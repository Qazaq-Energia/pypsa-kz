# SPDX-FileCopyrightText:  PyPSA-KZ Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Post-processing rules for the Kazakhstan model.
# Included via `custom_rules` in configs/kz/config.kz.yaml, so RDIR and
# config are inherited from the main Snakefile.

POSTDIR = "results/" + RDIR + "post-processing/"


rule plot_capacity_comparison:
    params:
        historic_year=config["kz"]["capacity_comparison"]["historic_year"],
        powerplants_filter=config["electricity"]["powerplants_filter"],
    input:
        network="networks/" + RDIR + "elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.nc",
        custom_powerplants=config["electricity"]["custom_powerplants"]["filepaths"],
        historic_capacities=config["kz"]["capacity_comparison"]["historic_capacities"],
    output:
        csv=POSTDIR + "capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.csv",
        plot=POSTDIR + "capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.png",
    log:
        "logs/"
        + RDIR
        + "post-processing/plot_capacity_comparison/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.log",
    benchmark:
        (
            "benchmarks/"
            + RDIR
            + "post-processing/plot_capacity_comparison/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}"
        )
    resources:
        mem_mb=4000,
    script:
        "../../scripts/kz/post-processing/plot_capacity_comparison.py"


rule post_process_all:
    input:
        expand(
            POSTDIR + "capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.{ext}",
            **config["scenario"],
            ext=["csv", "png"],
        ),
