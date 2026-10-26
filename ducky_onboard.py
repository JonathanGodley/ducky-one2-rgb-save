"""Save a solid colour into a Ducky One 2 RGB's on-board memory (USB 04d9:0348).

Rewrites the active profile with only the "100% Full Backlit" slot's colour changed, makes
that mode active and commits it, the way Ducky RGB v1.32 saves. The colour survives a power
cycle. Protocol notes: PROTOCOL.md.

  python ducky_onboard.py backup               read the active profile into backups/ (no memory write)
  python ducky_onboard.py set 0000FF           back up, then save the colour and select the mode
  python ducky_onboard.py set 0000FF --dry-run show what would be written, write nothing
  python ducky_onboard.py restore <backup.json> write a backup back to its profile
"""
import argparse
import datetime
import json
import pathlib
import sys
import time

import hid

VID, PID = 0x04D9, 0x0348
USAGE_PAGE, USAGE = 0xFF00, 0x0001
SLOTS = 28
TYPE_OFF, TYPE_STATIC_ALL = 0x0010, 0x0100
BACKUP_DIR = pathlib.Path(__file__).with_name("backups")


class Ducky:
    def __init__(self):
        path = next((d["path"] for d in hid.enumerate(VID, PID)
                     if d["usage_page"] == USAGE_PAGE and d["usage"] == USAGE), None)
        if path is None:
            sys.exit("Ducky One 2 RGB (04d9:0348) vendor interface not found")
        self.dev = hid.device()
        self.dev.open_path(path)

    def close(self):
        self.dev.close()

    def cmd(self, payload, timeout_ms=1000):
        """Send a 64-byte payload and return the 64-byte reply whose first 4 bytes echo it."""
        pkt = bytes(payload) + bytes(64 - len(payload))
        self.dev.write(b"\x00" + pkt)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            r = bytes(self.dev.read(65, 50))
            if not r:
                continue
            if len(r) == 65 and r[0] == 0 and r[1:5] == pkt[:4]:
                r = r[1:]
            if r[:4] == pkt[:4]:
                time.sleep(0.002)
                return r
        raise RuntimeError(f"no reply to {pkt[:4].hex(' ')}")

    def select_profile(self, p):
        self.cmd([0x51, 0x00, 0x00, 0x00, p])
        for _ in range(10):
            if self.cmd([0x52, 0x00])[4] == p:
                return
            time.sleep(0.05)
        raise RuntimeError(f"profile {p} not selected")


def parse_slot(entries, blob, s):
    """Return [(record byte offset, type id)] for slot s."""
    e = entries[s]
    cnt, xw, off = e[0], e[1], int.from_bytes(e[2:4], "little")
    if cnt == 0:
        return []
    d = (off + xw + (1 if cnt > 1 else 0)) * 4
    recs = []
    for i in range(cnt):
        rec = int.from_bytes(blob[d + 4 * i:d + 4 * i + 2], "little") * 4
        recs.append((rec, int.from_bytes(blob[rec:rec + 2], "little")))
    return recs


def blob_len(entries):
    end = 0
    for e in entries:
        cnt, xw, off = e[0], e[1], int.from_bytes(e[2:4], "little")
        if cnt:
            end = max(end, (off + xw + (1 if cnt > 1 else 0) + cnt) * 4)
    return end


def read_profile(k):
    """Enter programming mode and read the active profile. Leaves the keyboard in programming mode."""
    info = {"version": k.cmd([0x12, 0x20])[4:36].hex()}
    p = k.cmd([0x52, 0x00])[4]
    k.cmd([0x41, 0x03])
    k.select_profile(p)
    name = k.cmd([0x52, 0x01, p, 0x00])[4:]
    active = k.cmd([0x52, 0x28])[4]
    geo = k.cmd([0x56, 0x00])[4:20]
    if geo[11] != SLOTS:
        raise RuntimeError(f"unexpected geometry {geo.hex(' ')}")
    if k.cmd([0x56, 0x02, 0x01])[4:6] != TYPE_STATIC_ALL.to_bytes(2, "little"):
        raise RuntimeError("mode table entry 1 is not Static All")
    entries = [k.cmd([0x56, 0x14, s, 0x00])[4:12] for s in range(SLOTS)]
    n = -(-blob_len(entries) // 60)
    if not 0 < n <= geo[4]:
        raise RuntimeError(f"blob needs {n} packets, keyboard allows {geo[4]}")
    blob = b"".join(k.cmd([0x56, 0x20, i & 0xFF, i >> 8])[4:64] for i in range(n))
    return dict(info, profile=p, name=name.hex(), active_slot=active, geometry=geo.hex(),
                entries=[e.hex() for e in entries], blob=blob.hex())


def save_backup(prof):
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = BACKUP_DIR / f"profile{prof['profile']}_{stamp}.json"
    path.write_text(json.dumps(prof, indent=1))
    return path


def write_profile(k, prof, active_slot):
    """Write directory and blob to the (already selected) profile, set its active slot, commit."""
    p = prof["profile"]
    entries = [bytes.fromhex(e) for e in prof["entries"]]
    blob = bytes.fromhex(prof["blob"])
    n = -(-blob_len(entries) // 60)
    k.cmd([0x51, 0x01, p, 0x00, *bytes.fromhex(prof["name"])])
    for s, e in enumerate(entries):
        k.cmd([0x56, 0x15, s, 0x00, *e])
    for i in range(n):
        k.cmd([0x56, 0x21, i & 0xFF, i >> 8, *blob[i * 60:(i + 1) * 60]])
    k.cmd([0x51, 0x28, 0x00, 0x00, active_slot])
    k.cmd([0x50, 0x55], timeout_ms=3000)
    return n


def finish(k, p):
    k.select_profile(p)
    time.sleep(0.1)
    k.cmd([0x41, 0x00])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("backup")
    s = sub.add_parser("set")
    s.add_argument("rgb", help="colour as RRGGBB, e.g. 0000FF")
    s.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("file")
    a = ap.parse_args()

    k = Ducky()
    try:
        if a.action == "restore":
            prof = json.loads(pathlib.Path(a.file).read_text())
            p = k.cmd([0x52, 0x00])[4]
            if p != prof["profile"]:
                sys.exit(f"keyboard is on profile {p}, backup is profile {prof['profile']}; switch with Fn+number first")
            k.cmd([0x41, 0x03])
            k.select_profile(p)
            n = write_profile(k, prof, prof["active_slot"])
            finish(k, p)
            print(f"restored profile {p} ({n} blob packets), active slot {prof['active_slot']}")
            return

        prof = read_profile(k)
        path = save_backup(prof)
        p = prof["profile"]
        print(f"firmware {prof['version']}, profile {p}, active slot {prof['active_slot']}; backup {path}")
        if a.action == "backup":
            finish(k, p)
            return

        rgb = bytes.fromhex(a.rgb)
        entries = [bytes.fromhex(e) for e in prof["entries"]]
        blob = bytearray.fromhex(prof["blob"])
        # Full Backlit is a lone Static All record (as on the tested board) or Off + Static All
        # (profiles re-saved by Ducky's software, as in the published USB captures).
        matches = [t for t in range(SLOTS)
                   if sorted(ty for _, ty in parse_slot(entries, blob, t))
                   in ([TYPE_STATIC_ALL], [TYPE_OFF, TYPE_STATIC_ALL])]
        if len(matches) != 1:
            finish(k, p)
            sys.exit(f"expected one 100% Full Backlit slot, found {matches}; nothing written")
        target = matches[0]
        rec = next(o for o, ty in parse_slot(entries, blob, target) if ty == TYPE_STATIC_ALL)
        print(f"Full Backlit is slot {target}; colour {bytes(blob[rec + 8:rec + 11]).hex()} -> {rgb.hex()}"
              f" (record at blob byte {rec}, brightness byte {blob[rec + 11]:02x})")
        if a.dry_run:
            finish(k, p)
            print("dry run: nothing written")
            return
        blob[rec + 8:rec + 11] = rgb
        prof["blob"] = blob.hex()
        n = write_profile(k, prof, target)
        finish(k, p)
        print(f"saved: {n} blob packets written, active slot {target}, committed")
    except Exception:
        try:
            k.cmd([0x41, 0x00])  # don't leave the keyboard in programming mode
        except Exception:
            pass
        raise
    finally:
        k.close()


if __name__ == "__main__":
    main()
