# Roblox Cookie Extractor

This repo contains a Roblox cookie grabber that steals cookies and sends them to a Discord webhook. Don't forget to change the webhook URL in the script before you build it!

## What the script does

`roblox.py` searches a Windows computer for Roblox session cookies, including the `.ROBLOSECURITY` cookie. It looks in:

- Chrome, Edge, Brave, Opera, Opera GX, Vivaldi, and Yandex profiles
- Roblox Player and Studio data
- Roblox logs and registry entries
- Roblox UWP data
- Bloxstrap files
- Roblox LocalStorage data

The script also attempts to:

- Force-close browser processes
- Collect the computer name and public IP address
- Use discovered cookies to query Roblox account information
- Send cookies, account information, and system information to a configured Discord webhook or telemetry endpoint

## Status
Feel free to dm me on discord for any issues Korrektertyp#0000
