#!/bin/bash -l
# PBS -N EQdisc_4
# PBS -A NAML0001
# PBS -l walltime=12:00:00
# PBS -o Nudge4.out
# PBS -e Nudge4.out
# PBS -q premium
# PBS -l select=1:ncpus=10:mem=110GB
# PBS -m a
# PBS -M wchapman@ucar.edu

module load conda
conda activate npl-2023b

python ./Table1_ADF_RMSE_DA_stoch_05.py
