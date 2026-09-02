# pc-nerd-stats

A lightweight Python terminal dashboard for checking your PC stats in real time.

Built by **izzy.js**

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Preview

![pc-nerd-stats preview](https://media.discordapp.net/attachments/1362660922988036157/1544848717637746708/Screenshot_2026-09-02_191624.png?ex=6a99fffc&is=6a98ae7c&hm=abb12315554456252cd4db7fa15862910f8f1dde69db96c85486d29082fef38c&=&format=webp&quality=lossless)

## Features

* Live CPU usage
* CPU information and clock speed
* GPU detection
* NVIDIA GPU usage, VRAM, and temperature support
* RAM usage
* Storage usage
* Network upload/download speed
* Local IP address
* Display resolution
* Monitor refresh rate
* System uptime
* Live terminal dashboard
* Adjustable refresh rate

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/pc-nerd-stats.git
cd pc-nerd-stats
```

Install the required packages:

```bash
py -m pip install -r requirements.txt
```

## Usage

Start the live dashboard:

```bash
py main.py
```

Show one snapshot and exit:

```bash
py main.py --once
```

Change the refresh interval:

```bash
py main.py --interval 1
```

## Requirements

* Windows 10/11
* Python 3.10+
* `psutil`
* `rich`

NVIDIA GPU statistics use `nvidia-smi` when available.

Some temperature sensors may not be exposed by Windows and will display as unavailable.

## Planned

* Multiple GPU detection
* Top CPU/RAM processes
* Battery and power information
* Multiple drive support
* Public IP and ping
* Motherboard information
* Better AMD GPU statistics
* Game/process detection
* FPS monitoring
