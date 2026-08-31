#!/usr/bin/env python3
from __future__ import annotations

import atexit
import os
import sys
import time

# Settings retained from the original project.
useWSGI = False  # Historical name: this creates a Twisted service application.
port = 8080


def _force_project_working_directory():
    base = os.path.dirname(os.path.abspath(__file__))
    if base:
        os.chdir(base)


def _import_twisted():
    try:
        from twisted.internet import reactor
        from twisted.web import server
    except ImportError as exc:
        raise SystemExit(
            "Twisted is required to run the server. Install dependencies with: "
            "python3 -m pip install -r requirements.txt"
        ) from exc
    return reactor, server


class Log:
    class filesplit:
        def __init__(self):
            self.files = []

        def write(self, data):
            for output in self.files:
                output.write(data)
            return len(data)

        def flush(self):
            for output in self.files:
                output.flush()

    def __init__(self, reactor):
        self.reactor = reactor
        minutes, seconds = map(int, time.strftime("%M %S").split(" "))
        minutes = 59 - minutes
        seconds = 59 - seconds
        reactor.callLater(60 * minutes + seconds + 5, self.HandleUpdate)
        reactor.callLater(60 * 5, self.AutoFlush)
        self._open_handles()

        self.stderr = sys.stderr
        sys.stderr = self.filesplit()
        sys.stderr.files.extend((self.stderr, self.Errorhandle))
        self.write("Server startup...", True)

    def _open_handles(self):
        directory = time.strftime("logs/%Y/%B")
        os.makedirs(directory, exist_ok=True)
        self.Activityhandle = open(
            time.strftime("logs/%Y/%B/%d %B activity.log"), "a", encoding="utf-8"
        )
        self.Errorhandle = open(
            time.strftime("logs/%Y/%B/%d %B error.log"), "a", encoding="utf-8"
        )

    def HandleUpdate(self):
        self.reactor.callLater(60 * 60, self.HandleUpdate)
        print(time.strftime("[%H:%M:%S] Handle update"))
        old_error = self.Errorhandle
        self.Activityhandle.close()
        old_error.close()
        self._open_handles()
        if isinstance(sys.stderr, self.filesplit) and len(sys.stderr.files) > 1:
            sys.stderr.files[1] = self.Errorhandle

    def AutoFlush(self):
        self.reactor.callLater(60 * 5, self.AutoFlush)
        self.flush()

    def flush(self):
        for handle in (self.Activityhandle, self.Errorhandle):
            handle.flush()
            os.fsync(handle.fileno())

    def close(self):
        for handle in (self.Activityhandle, self.Errorhandle):
            if not handle.closed:
                handle.close()

    def write(self, String, Silent=False):
        line = str(String).rstrip("\n")
        if not Silent:
            print(time.strftime("[%H:%M:%S]"), line)
        self.Activityhandle.write(time.strftime("[%H:%M:%S] ") + line + "\n")

    Print = write



def create_site():
    _force_project_working_directory()
    reactor, twisted_server = _import_twisted()

    print("Initializing flipnote database...", end=" ", flush=True)
    import DB  # noqa: F401 - initialization is intentional
    print("Done!")

    log = Log(reactor)

    print("Setting up hatena site...", end=" ", flush=True)
    import hatena
    hatena.ServerLog = log

    class ProxyCompatibleSite(twisted_server.Site):
        """Accept the absolute-form request target sent by HTTP proxy clients."""

        def buildProtocol(self, addr):
            protocol = super().buildProtocol(addr)
            old_data_received = protocol.dataReceived

            def data_received(data):
                for check, repl in (
                    (b"GET http://flipnote.hatena.com", b"GET "),
                    (b"POST http://flipnote.hatena.com", b"POST "),
                ):
                    if check in data:
                        data = data.replace(check, repl)
                return old_data_received(data)

            protocol.dataReceived = data_received
            return protocol

    site = ProxyCompatibleSite(hatena.Setup())
    print("Done!")
    return reactor, site, log


def main():
    print("Importing modules...", end=" ", flush=True)
    _force_project_working_directory()
    reactor, site, log = create_site()
    print("Server start!\n")

    if useWSGI:
        from twisted.application import internet, service

        application = service.Application("web")
        internet.TCPServer(port, site).setServiceParent(service.IServiceCollection(application))
        atexit.register(log.write, String="Server shutdown", Silent=True)
        return application

    reactor.listenTCP(port, site)
    try:
        reactor.run()
    finally:
        log.write("Server shutdown", True)
        log.flush()
    return None


if __name__ == "__main__":
    main()
