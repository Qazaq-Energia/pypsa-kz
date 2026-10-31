# SPDX-FileCopyrightText:  PyPSA-KZ Authors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Post-processing rules for the Kazakhstan model.
# Included via `custom_rules` in configs/config.kz.default.yaml, so RDIR and
# config are inherited from the main Snakefile.

POSTDIR = "results/" + RDIR + "post-processing/"


rule plot_capacity_comparison:
    params:
        nice_names=config["plotting"]["nice_names"],
    input:
        network="results/"
        + RDIR
        + "networks/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.nc",
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
        "../../scripts/kz_model/post-processing/plot_capacity_comparison.py"


rule post_process_all:
    input:
        expand(
            POSTDIR + "capacities/elec_s{simpl}_{clusters}_ec_l{ll}_{opts}.{ext}",
            **config["scenario"],
            ext=["csv", "png"],
        ),
