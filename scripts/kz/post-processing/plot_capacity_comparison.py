# SPDX-FileCopyrightText:  PyPSA-KZ Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# -*- coding: utf-8 -*-
"""
Compares installed capacities per technology group of the electricity network
with the custom powerplant input and with historic statistics.

Relevant Settings
-----------------

.. code:: yaml

    electricity:
        powerplants_filter:
        custom_powerplants:
            filepaths:

    kz:
        capacity_comparison:
            historic_year:
            historic_capacities:

Inputs
------

- ``networks/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.nc``: prepared (not yet solved) network, confer :ref:`prepare`
- ``data/kz/custom_powerplants_*.csv``: custom powerplant files listed in ``electricity.custom_powerplants.filepaths``
- ``data/kz/historic_capacities.csv``: historic installed capacities with sources, see below

Outputs
-------

- ``results/{RDIR}post-processing/capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.csv``: capacities per technology group in MW
- ``results/{RDIR}post-processing/capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.png``: grouped bar chart in GW

Description
-----------

Three capacity sets are compared per technology group:

- ``historic_<year>``: official statistics read from ``historic_capacities.csv``
  for ``historic_year`` and ``zone == "KZ"``.
- ``input``: the custom powerplant files after applying ``powerplants_filter``,
  i.e. what should enter the model. Differences to ``historic`` show gaps in
  the data; differences to ``model`` show plants lost in the workflow (e.g.
  unmapped carriers, no bus found).
- ``model``: ``p_nom`` of generators and storage units in the network.

``gas_steam`` and ``gas_turbine`` are combined to ``gas_oil`` because both are
modelled as ``OCGT``.
"""

import matplotlib.pyplot as plt
import pandas as pd
import pypsa
from _helpers import configure_logging, create_logger, read_csv_nafix

logger = create_logger(__name__)

# model carrier -> technology group
CARRIER_GROUPS = {
    "coal": "coal",
    "lignite": "coal",
    "CCGT": "gas_oil",
    "OCGT": "gas_oil",
    "oil": "gas_oil",
    "hydro": "hydro",
    "ror": "hydro",
    "PHS": "hydro",
    "onwind": "wind",
    "offwind-ac": "wind",
    "offwind-dc": "wind",
    "solar": "solar",
    "biomass": "biomass",
}

# Fueltype of custom powerplants -> technology group
FUELTYPE_GROUPS = {
    "Hard Coal": "coal",
    "Lignite": "coal",
    "CCGT": "gas_oil",
    "OCGT": "gas_oil",
    "Natural Gas": "gas_oil",
    "Oil": "gas_oil",
    "Hydro": "hydro",
    "Wind": "wind",
    "Solar": "solar",
    "Bioenergy": "biomass",
}

# group in historic statistics -> technology group
HISTORIC_GROUPS = {
    "coal": "coal",
    "gas_steam": "gas_oil",
    "gas_turbine": "gas_oil",
    "hydro": "hydro",
    "wind": "wind",
    "solar": "solar",
    "biomass": "biomass",
}

GROUP_NAMES = {
    "coal": "Coal",
    "gas_oil": "Gas & oil",
    "hydro": "Hydro",
    "wind": "Wind",
    "solar": "Solar",
    "biomass": "Biomass",
}

# components contributing to generation capacity
COMPONENTS = ["Generator", "StorageUnit"]

# carriers which do not represent physical assets
EXCLUDE_CARRIERS = ["load", "load shedding"]

COLORS = ["#9e9e9e", "#4c78a8", "#f58518"]


def get_historic_capacities(fn: str, year: int, zone: str = "KZ") -> pd.Series:
    """
    Read historic capacities per technology group for ``year`` and ``zone``.

    Parameters
    ----------
    fn : str
        Path to the historic capacities csv.
    year : int
        Statistics year.
    zone : str
        Zone, ``"KZ"`` for the national total.

    Returns
    -------
    pd.Series
        Capacities in MW indexed by technology group.
    """
    df = pd.read_csv(fn)
    df = df.loc[(df["year"] == year) & (df["zone"] == zone)]
    # drops the aggregates "thermal" and "total" to avoid double counting
    df = df.loc[df["group"].isin(HISTORIC_GROUPS)]

    if df.empty:
        raise ValueError(f"No historic capacities for year {year} and zone {zone} in {fn}.")

    for source in df["source"].dropna().unique():
        logger.info(f"Historic capacities {year}: {source}")

    capacities = df.groupby(df["group"].map(HISTORIC_GROUPS))["capacity_mw"].sum()
    return capacities.rename(f"historic_{year}")


def get_input_capacities(fns: list[str], query: str | None) -> pd.Series:
    """
    Get capacities per technology group of the custom powerplant files after
    applying the powerplants filter.

    Parameters
    ----------
    fns : list[str]
        Paths to custom powerplant files.
    query : str or None
        ``electricity.powerplants_filter``.

    Returns
    -------
    pd.Series
        Capacities in MW indexed by technology group.
    """
    ppl = pd.concat(
        [read_csv_nafix(fn, index_col=0, dtype={"bus": "str"}) for fn in fns],
        ignore_index=True,
    )
    if query:
        ppl = ppl.query(query)

    unknown = set(ppl["Fueltype"].dropna()) - set(FUELTYPE_GROUPS)
    if unknown:
        logger.warning(f"Fueltypes without technology group are ignored: {unknown}")

    capacities = ppl.groupby(ppl["Fueltype"].map(FUELTYPE_GROUPS))["Capacity"].sum()
    return capacities.rename("input")


def get_model_capacities(n: pypsa.Network) -> pd.Series:
    """
    Get installed capacities (``p_nom``) per technology group.

    Parameters
    ----------
    n : pypsa.Network
        Network.

    Returns
    -------
    pd.Series
        Capacities in MW indexed by technology group.
    """
    capacities = n.statistics.installed_capacity(
        comps=COMPONENTS, groupby="carrier", nice_names=False
    )
    capacities = capacities.groupby(level="carrier").sum()
    capacities = capacities.drop(EXCLUDE_CARRIERS, errors="ignore")

    unknown = set(capacities.index) - set(CARRIER_GROUPS)
    if unknown:
        logger.warning(f"Carriers without technology group are ignored: {unknown}")

    capacities = capacities.groupby(capacities.index.map(CARRIER_GROUPS)).sum()
    return capacities.rename("model")


def plot_capacities(capacities: pd.DataFrame, fn: str) -> None:
    """
    Plot capacities per technology group as a grouped bar chart in GW.

    Parameters
    ----------
    capacities : pd.DataFrame
        Capacities in MW with technology groups as index.
    fn : str
        Output path of the figure.
    """
    df = capacities.div(1e3).rename(index=lambda c: GROUP_NAMES.get(c, c))
    df = df.sort_values(df.columns[0], ascending=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    df.plot.bar(ax=ax, width=0.8, color=COLORS, edgecolor="none")

    ax.set_ylabel("Capacity [GW]")
    ax.set_xlabel("")
    ax.set_title("Installed capacity: historic vs. input vs. model")
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", alpha=0.3)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(fn, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    if "snakemake" not in globals():
        from pathlib import Path

        from _helpers import mock_snakemake

        snakemake = mock_snakemake(
            "plot_capacity_comparison",
            root_dir=Path(__file__).resolve().parents[3],
            configfiles=["configs/kz/config.kz.yaml"],
            simpl="",
            clusters="17",
            ll="v1.0",
            opts="1h",
        )

    configure_logging(snakemake)

    historic_year = snakemake.params.historic_year

    historic = get_historic_capacities(
        snakemake.input.historic_capacities, historic_year
    )
    inputs = get_input_capacities(
        list(snakemake.input.custom_powerplants),
        snakemake.params.powerplants_filter,
    )
    model = get_model_capacities(pypsa.Network(snakemake.input.network))

    capacities = pd.concat([historic, inputs, model], axis=1).fillna(0.0)
    capacities.index.name = "group"
    capacities = capacities.loc[(capacities != 0).any(axis=1)]
    capacities.loc["total"] = capacities.sum()

    capacities["input_vs_historic_%"] = (
        capacities["input"] / capacities[historic.name] - 1
    ).mul(100)
    capacities["model_vs_input_%"] = (capacities["model"] / capacities["input"] - 1).mul(100)

    logger.info(f"Capacities [MW]:\n{capacities.round(1)}")

    capacities.round(2).to_csv(snakemake.output.csv)
    plot_capacities(
        capacities.drop("total")[[historic.name, "input", "model"]],
        snakemake.output.plot,
    )
