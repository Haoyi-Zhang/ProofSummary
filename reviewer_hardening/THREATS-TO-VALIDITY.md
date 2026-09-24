
## Availability and parser validity

The semantic proof assumes a certificate has been parsed, but a release checker
must also bound the cost of reaching that point.  The bounded entry point caps
input bytes and decoded structure, rejects non-strict JSON and floats, and
turns parser recursion into a checked rejection.  This does not make the
checker immune to every operating-system denial-of-service mechanism; it makes
the repository's accepted-input resource envelope explicit and executable.

## Independence terminology

“Independent checker” in the paper means implementation-separated from the
producer and search engine, with its own recurrence reconstruction and witness
replay.  It does not mean an independently authored third-party checker.  The
base artifact's dense expansion checker adds representation diversity, but
external replication remains a separate validity objective.
