"""
BlueapiClient pre configured in an iPython environment.
Running plans will show the progress of the plan via each event.
It also has the ability to plot data afterwards. Useful for development
to quickly test devices and plans are working correctly.

Connect to real beamline:
$ export BEAMLINE=iXX
$ python src/sm_bluesky/scripts/clients/blueapi_client.py

Connect to beamline in mock mode
1. Create a config file. Example:

api:
    url: http://0.0.0.0:8000
env:
    metadata:
        instrument: iXX
    sources:
        - kind: deviceManager
        module: dodal.beamlines.iXX
        mock: True
        - kind: planFunctions
        module: dodal.plans
        - kind: planFunctions
        module: dodal.plan_stubs.wrapped
stomp:
    enabled: true
    url: tcp://localhost:61613/

2. Start stomp (note, not compatible running with GDA in dummy mode at the same time.)
$ ml dasctools
$ activemq-for-dummy

3. In one termianl, start a mock server.
$ ml uv
$ uv run blueapi -c /path/config.yaml serve

4. In another terminal, start the client script and point to same config
$ python src/sm_bluesky/scripts/clients/blueapi_client.py --config /path/config.yaml
"""

from datetime import datetime
from os import environ
from pathlib import Path
from typing import Any

import click
from blueapi.client import BlueapiClient
from blueapi.client.event_bus import AnyEvent
from blueapi.config import (
    ApplicationConfig,
    ConfigLoader,
    HttpUrl,
    RestConfig,
    StompConfig,
    TcpUrl,
)
from blueapi.core import DataEvent

from imaging_bluesky._version import __version__

data: dict[str, dict[str, list[Any]]] = {}


def _default_config(beamline: str) -> ApplicationConfig:
    return ApplicationConfig(
        api=RestConfig(
            url=HttpUrl(f"https://{beamline}-blueapi.diamond.ac.uk"),
        ),
        stomp=StompConfig(
            enabled=True,
            url=TcpUrl(f"tcp://{beamline}-rabbitmq-daq.diamond.ac.uk:61613"),
        ),
    )


def _format_time(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _load_config(config_path: Path | None) -> ApplicationConfig:
    if config_path is not None:
        click.echo(f"Starting BlueAPI client from config file {config_path}.")
        loader = ConfigLoader(ApplicationConfig)
        loader.use_values_from_yaml(config_path)
        return loader.load()

    beamline = environ.get("BEAMLINE")
    if beamline is None:
        raise click.ClickException(
            "BEAMLINE environment variable not set and no config file was supplied."
        )
    click.echo(f"Starting BlueAPI client for {beamline}.")
    return _default_config(beamline)


def _install_feedback_callback(bc: BlueapiClient) -> None:
    """Install a callback which displays run progress."""

    current_scan_id: Any | None = None

    def feedback(event: AnyEvent) -> None:
        nonlocal current_scan_id

        match event:
            case DataEvent(
                name="start", doc={"scan_id": scan_id, "uid": uid, "time": time}
            ):
                current_scan_id = scan_id
                data[scan_id] = {}

                click.echo(
                    f"{_format_time(time)} - Run started (scan_id={scan_id}, uid={uid})"
                )

            case DataEvent(
                name="stop",
                doc={
                    "exit_status": status,
                    "time": time,
                    "uid": uid,
                },
            ):
                click.echo(
                    f"{_format_time(time)} - Run complete (scan_id={current_scan_id}, "
                    f"uid: {uid}): {status}"
                )
                current_scan_id = None

            case DataEvent(
                name="event",
                doc={"seq_num": point, "data": event_data, "time": time},
            ):
                if current_scan_id is None:
                    return

                scan_data = data[current_scan_id]

                for device, value in event_data.items():
                    scan_data.setdefault(device, []).append(value)

                values = ", ".join(
                    f"{name}={value}" for name, value in event_data.items()
                )
                click.echo(f"{_format_time(time)} - Point {point}: {values}")

    callback_id = bc.add_callback(feedback)
    click.echo(f"Installed data event callback (id={callback_id}).")


def plot_scan(
    scan_id: Any,
    x_axis: str,
    y_axis: str,
) -> None:
    import matplotlib.pyplot as plt

    """Plot two axes from a scan against each other."""
    try:
        scan_data = data[scan_id]
    except KeyError as e:
        raise ValueError(
            f"Scan {scan_id} not found. Available scans: {list(data)}"
        ) from e

    for axis in (x_axis, y_axis):
        if axis not in scan_data:
            raise ValueError(
                f"Axis {axis!r} not found in scan {scan_id}. "
                f"Available axes: {list(scan_data)}"
            )

    plt.ion()
    plt.plot(
        scan_data[x_axis],
        scan_data[y_axis],
        marker="o",
    )
    plt.xlabel(x_axis)
    plt.ylabel(y_axis)
    plt.title(f"Scan {scan_id}")
    plt.show()


def _setup_client(config: ApplicationConfig) -> BlueapiClient:
    """Create and initialise the BlueAPI client."""
    bc = BlueapiClient.from_config(config)
    click.echo("Logging in...")
    bc.login()

    _install_feedback_callback(bc)

    click.echo("\nPlans available:")
    for plan in bc.plans:
        click.echo(f"  {plan.name}")

    click.echo("\nDevices available:")
    for device in bc.devices:
        click.echo(f"  {device.name}")

    click.echo(
        "\nPlease remember to configure the correct "
        "`bc.instrument_session` before running a plan."
    )
    return bc


def _start_interactive_shell(bc: BlueapiClient) -> None:
    from IPython import embed

    """Start an interactive IPython shell with the BlueAPI client available."""
    embed(
        header="\nBlueAPI client ready.\n"
        'The client is available as "bc".\n'
        "Use exit() or Ctrl-D to leave.\n",
        user_ns={
            "bc": bc,
            "pl": bc.plans,
            "dev": bc.devices,
            "scan_data": data,
            "plot_scan": plot_scan,
        },
    )


@click.command()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "-f",
    type=click.Path(
        path_type=Path,
        exists=True,
        dir_okay=False,
        readable=True,
    ),
    help="Path to a custom BlueAPI configuration file.",
)
def main(config: Path | None) -> None:
    """Start an interactive BlueAPI client."""
    blueapi_config = _load_config(config)
    bc = _setup_client(blueapi_config)
    _start_interactive_shell(bc)


if __name__ == "__main__":
    main()
