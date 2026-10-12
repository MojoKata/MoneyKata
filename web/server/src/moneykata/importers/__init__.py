"""Reading the files users bring (requirements §4.3): OFX and QFX with ofxtools, and CSV
with a saved column mapping. A reader turns a file into a ParsedFile; store/repos/imports.py
applies it to an account, idempotently."""
