# Ducky One 2 RGB (04d9:0348) on-board lighting protocol

Worked out from a Ghidra decompile of Ducky RGB v1.32 (`DuckyRGBSeries.exe`, Ducky's official software for the full-size One 2 RGB, DKON1808ST), cross-checked against USB captures of that software on 0348 boards attached to OpenRGB issue #79 and in PascalDutch/duckylights. Tested on one board (firmware V1.01.05) on 2026-10-27: saving a colour into the Full Backlit slot and committing survives a power cycle.

## Transport

- Vendor HID interface: usage page `0xFF00`, usage `0x0001` (interface 1).
- Every command is a 64-byte payload sent as report ID `00` + 64 bytes. The keyboard answers each with a 64-byte report whose first 4 bytes echo the command; data starts at reply byte 4. Wait for the echo before sending the next command.
- `50 55` takes about 50 ms to answer; everything else about 2 ms.

## Commands

`p` = profile 0..5, `s` = slot 0..27, `k` = packet index (u16 LE in bytes 2-3).

| bytes | meaning |
|---|---|
| `12 20` | info page; reply = length byte + UTF-16 firmware version |
| `41 03` | enter programming mode (before profile reads or writes) |
| `41 01` / `41 80` | software-control / live-preview modes |
| `41 00` | hand control back to the on-board lighting |
| `52 00` | read current profile (reply[4]) |
| `51 00 00 00 p` | select profile; poll `52 00` until it reads back `p` |
| `52 01 p 00` / `51 01 p 00 <60 B>` | read / write profile name |
| `52 28` / `51 28 00 00 s` | read / set the profile's active slot (`FF` = live buffer) |
| `56 00` | geometry: reply[8] = max blob packets (42), reply[15] = slots (28) |
| `56 02 i` | mode-table entry i (u16 type id first) |
| `56 14 s 00` / `56 15 s 00 <8 B>` | read / write directory entry s |
| `56 20 k` / `56 21 k <60 B>` | read / write blob packet k |
| `50 55` | commit the selected profile to flash |
| `56 81` … `56 83` … `51 28 00 00 FF` | live upload (what OpenRGB "Direct" uses); not stored |

**Never send:** `11 xx` (enters the bootloader), `10 xx` and `1E xx` (firmware updater), `50 10` (appears to reset a profile), anything to PID `0x1348` (the bootloader's identity).

## Storage

Each profile has its own 28-entry directory and blob; writing one profile leaves the others alone. No checksums.

- **Directory entry** (8 bytes): `[record count][extra descriptor words][u16 LE descriptor offset, in 4-byte words] AA AA AA AA`.
- **Blob**: 60-byte packets. Per slot: records, then 20-byte key masks (all `FF` = all keys), then the descriptor: the extra words, then (if more than one record) one u32 of mask offsets, then one u32 per record (low 16 bits = record offset in words, high 16 = layer).
- **Record header** (16 bytes; Off is 8): bytes 0-1 type id (LE), byte 3 `C1` on the base layer, bytes 8-10 R G B, byte 11 `FF`.
- **Type ids** (LE u16): Off `0x0010`, Static All `0x0100`, Static List (per-key, CM1/CM2) `0x0180`, Breath `0x3000`, Color Cycle `0x3100`, Wave `0x3200`, Triangle `0x3220`, Snake Stack `0x3310`, Random R `0x4008`, Single `0x8000`, Single Rand `0x8004`, Laser `0x8100`, Ripple v2 `0x8201`.

Layout on the tested board, never re-saved by Ducky's software: slots 0-1 CM1/CM2, then one record per slot in the manual's mode order: 2 Wave, 3 Triangle, 4 Snake Stack, 5 Color Cycle, 6 Random R, 7 Ripple v2, 8 Single Rand, 9 Laser, 10 Single, 11 Breath, **12 Static All (100% Full Backlit)**, 13 Off. Profiles re-saved by Ducky's software can instead hold two-record slots, e.g. Full Backlit as Off + Static All.

## Save sequence (Ducky's software, per profile)

`41 03`; `51 00 00 00 p` + poll; `51 01 p 00 <name>`; `56 15` for all 28 entries; `56 21` for every blob packet; `51 28 00 00 <active slot>`; `50 55`. On exit: `51 00 00 00 <current p>`, wait 100 ms, `41 00`.
