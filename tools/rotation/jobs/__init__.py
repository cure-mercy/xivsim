"""The job models. JOBS keys them as the command lines name them (`--job rpr`): {key: (module, FFLogs' job name)},
in the order they were added. Every module registered here is imported by every search worker, so a job goes in only
once `python -c "from jobs import <job>"` passes."""
from . import blm, rpr, mnk, brd, drg, rdm, vpr, sam, pct, mch, nin, smn, dnc

JOBS = {m.__name__.rsplit(".", 1)[1]: (m, m.LOG_NAME) for m in (blm, rpr, mnk, brd, drg, rdm, vpr, sam, pct, mch, nin, smn, dnc)}
