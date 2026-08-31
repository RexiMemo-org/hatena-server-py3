DB_type = "plaintext"  # "plaintext" or future backends

if DB_type == "plaintext":
    from database import Database
elif DB_type == "mondoDB":  # legacy placeholder; not implemented
    from database import Database
else:
    import sys
    print('Unsupported database type "%s"' % DB_type)
    sys.exit(1)
