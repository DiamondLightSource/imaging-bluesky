[![CI](https://github.com/DiamondLightSource/imaging-bluesky/actions/workflows/ci.yml/badge.svg)](https://github.com/DiamondLightSource/imaging-bluesky/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/DiamondLightSource/imaging-bluesky/branch/main/graph/badge.svg)](https://codecov.io/gh/DiamondLightSource/imaging-bluesky)
[![PyPI](https://img.shields.io/pypi/v/imaging-bluesky.svg)](https://pypi.org/project/imaging-bluesky)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# imaging_bluesky

Bluesky plans and tools for the Imaging Group

Source          | <https://github.com/DiamondLightSource/imaging-bluesky>
:---:           | :---:
PyPI            | `pip install imaging-bluesky`
Docker          | `docker run ghcr.io/diamondlightsource/imaging-bluesky:latest`
Releases        | <https://github.com/DiamondLightSource/imaging-bluesky/releases>

# Data Collection in the Training Rigs

## Running the IPython Terminal

1. Open **VSCode** with the container.
2. Open a terminal inside the **VSCode container**.
3. Run the following command:

   ```bash
   ipython -i startup_p49.py
    ```
3. To run a scan in the IPython terminal:
    ```python
    RE(fly_scan(0, 10, 11, 1, stages.x, panda_device))
    ```
## Retrieving data

1. SSH into the Beamline server
2. Navigate to the data directory:
   ```bash
   cd /exports/mybeamline/data
    ```
3. Copy the data file to your home directory:
   ```bash
   cp p49-X-panda.h5 ~/
    ```
4. Open the .h5 file in **DAWN** for analysis.
