# ducky-one2-rgb-save

Save a solid colour into a **Ducky One 2 RGB**'s own memory over USB, so it stays after unplugging, a restart or a power cut. No Ducky software, and no app running in the background.

> **Vibe coded. Run it at your own risk.**
> This was written with an AI assistant (Claude), from a decompile of Ducky's software and other people's USB captures. It has been tested on exactly one keyboard. It writes to your keyboard's flash memory. It might do nothing, mess up your lighting profile, or worse. No warranty of any kind; see [LICENSE](LICENSE).

## Why

Ducky's on-keyboard combos work, but some of us would rather not press Fn+F10 ten times. [OpenRGB](https://openrgb.org) can colour the One 2 RGB, but only live: the colour is gone when the keyboard loses power and it goes back to its rainbow. Ducky's own Windows app (Ducky RGB v1.32) can save to the keyboard, but it's from 2019 and unsigned.

This script does what Ducky's app does when it saves, and nothing else.

## What it does

The keyboard stores 6 profiles, each holding its lighting modes (the ones you cycle with Fn+F10). `set` takes the active profile and:

1. reads it and saves a backup to `backups/`,
2. changes the colour of the **100% Full Backlit** mode only,
3. makes that the active mode,
4. writes the profile back and commits it to flash.

Your other modes and profiles stay as they were.

## Tested on

- Ducky One 2 RGB, full size (DKON1808ST), USB ID `04d9:0348`, firmware V1.01.05
- Windows 11, Python 3.14

Other keyboards that share that USB ID (the Ducky Shine 7 does) may work, but haven't been tried. The One 2 RGB TKL (`04d9:0356`), the One 2 Mini/SF and the One 3 are **not** supported. The script refuses any other USB ID.

## Use

```
pip install hidapi
python ducky_onboard.py backup                  # read the active profile into backups/, change nothing
python ducky_onboard.py set 0000FF --dry-run    # show what would change, write nothing
python ducky_onboard.py set 0000FF              # save blue and switch to 100% Full Backlit
python ducky_onboard.py restore backups/<file>.json
```

Close OpenRGB, SignalRGB or Ducky's app first; they fight over the keyboard. The colour is `RRGGBB` hex.

The script stops without writing if the profile doesn't look like it expects: an unexpected number of mode slots, or anything other than exactly one 100% Full Backlit mode.

## If it goes wrong

- `restore` writes a backup back to its profile.
- Holding **both Windows keys for 3 seconds** resets the keyboard's lighting to factory settings (from Ducky's manual). Whether that recovers a badly written profile is untested.
- Unplugging and replugging should get the keyboard out of a half-finished state.

## How it works

[PROTOCOL.md](PROTOCOL.md) covers the HID commands, how a profile is stored, and the commands to **never send**, including the ones that start a firmware update.

## Credits

- [OpenRGB](https://gitlab.com/CalcProgrammer1/OpenRGB): the live-colour protocol, and the Shine 7 USB captures attached to issue #79.
- [PascalDutch/duckylights](https://github.com/PascalDutch/duckylights): protocol notes and a captured save from Ducky's software.
- OpenRGB merge request !3748 (the older Ducky One, PID 0245), which labels the same save command.

## License

MIT
