# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText:  PyPSA-KZ Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# -*- coding: utf-8 -*-
"""
Compares historic, installed and optimal capacities per carrier of a solved
network.

Relevant Settings
-----------------

.. code:: yaml

    plotting:
        nice_names:

.. seealso::
    Documentation of the configuration file ``config.yaml`` at
    :ref:`plotting_cf`

Inputs
------

- ``results/networks/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.nc``: solved PyPSA network, confer :ref:`solve`

Outputs
-------

- ``results/post-processing/capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.csv``: capacities per carrier in MW
- ``results/post-processing/capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.png``: grouped bar chart in GW

Description
-----------

The script reads installed (``p_nom``) and optimal (``p_nom_opt``) capacities
per carrier from the generators and storage units of a solved network and
compares them with historic capacities of ``HISTORIC_YEAR``. Historic values
are set in ``HISTORIC_CAPACITIES``. Carriers which are zero in all columns are
dropped.
"""

import sys
from pathlib import Path

# the script lives in a nested directory, make scripts/_helpers.py importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import pypsa
from _helpers import configure_logging, create_logger

logger = create_logger(__name__)

HISTORIC_YEAR = 2023

# Historic installed capacities in Kazakhstan for HISTORIC_YEAR [MW]
# TODO: dummy values, replace with official statistics
HISTORIC_CAPACITIES = {
    "coal": 13000.0,
    "CCGT": 2500.0,
    "OCGT": 1500.0,
    "oil": 1000.0,
    "hydro": 2800.0,
    "onwind": 1400.0,
    "solar": 1300.0,
}

# components contributing to generation capacity
COMPONENTS = ["Generator", "StorageUnit"]

# carriers which do not represent physical assets
EXCLUDE_CARRIERS = ["load", "load shedding"]

COLORS = ["#9e9e9e", "#4c78a8", "#f58518"]


def get_model_capacities(n: pypsa.Network) -> pd.DataFrame:
    """
    Get installed and optimal capacities per carrier.

    Parameters
    ----------
    n : pypsa.Network
        Solved network.

    Returns
    -------
    pd.DataFrame
        Capacities in MW with carriers as index and columns
        ``installed`` and ``optimal``.
    """
    kwargs = dict(comps=COMPONENTS, groupby="carrier", nice_names=False)

    installed = n.statistics.installed_capacity(**kwargs)
    optimal = n.statistics.optimal_capacity(**kwargs)

    capacities = pd.concat({"installed": installed, "optimal": optimal}, axis=1)
    capacities = capacities.groupby(level="carrier").sum()

    return capacities.drop(EXCLUDE_CARRIERS, errors="ignore")


def get_historic_capacities() -> pd.Series:
    """
    Get historic capacities per carrier for HISTORIC_YEAR in MW.
    """
    return pd.Series(HISTORIC_CAPACITIES, name=f"historic_{HISTORIC_YEAR}")


def plot_capacities(capacities: pd.DataFrame, nice_names: dict, fn: str) -> None:
    """
    Plot capacities per carrier as a grouped bar chart in GW.

    Parameters
    ----------
    capacities : pd.DataFrame
        Capacities in MW with carriers as index.
    nice_names : dict
        Mapping of carrier names to display names.
    fn : str
        Output path of the figure.
    """
    df = capacities.div(1e3).rename(index=lambda c: nice_names.get(c, c))
    df = df.sort_values(df.columns[-1], ascending=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    df.plot.bar(ax=ax, width=0.8, color=COLORS, edgecolor="none")

    ax.set_ylabel("Capacity [GW]")
    ax.set_xlabel("")
    ax.set_title("Historic vs. installed vs. optimal capacity")
    ax.tick_params(axis="x", rotation=45)
    plt.setp(ax.get_xticklabels(), ha="right")
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(fn, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_capacity_comparison",
            root_dir=Path(__file__).resolve().parents[3],
            configfiles=["configs/config.kz.default.yaml"],
            simpl="",
            clusters="17",
            ll="v1.0",
            opts="1h",
        )

    configure_logging(snakemake)

    nice_names = snakemake.params.nice_names

    n = pypsa.Network(snakemake.input.network)

    model_capacities = get_model_capacities(n)
    historic_capacities = get_historic_capacities()

    capacities = pd.concat([historic_capacities, model_capacities], axis=1)
    capacities = capacities.fillna(0.0)
    capacities.index.name = "carrier"

    # drop carriers which are zero everywhere, e.g. offshore wind
    capacities = capacities.loc[(capacities != 0).any(axis=1)]

    logger.info(f"Capacities [MW]:\n{capacities.round(1)}")

    capacities.to_csv(snakemake.output.csv)
    plot_capacities(capacities, nice_names, snakemake.output.plot)
