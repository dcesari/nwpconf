# Copyright (C) 2015 Davide Cesari
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

## @file
## @brief Module with utilities for parallel computing and batch scheduling.
## @details This module provides some functions that help in
## performing operations related to parallel computing and interaction
## with a batch scheduler, such as defining a Cartesian topology and
## starting parallel MPI executables in an MPI implementation- and
## scheduler-independent way. It is an optional module and it has to
## be sourced after the main _nwpconf.sh_ module.


## @fn parcomp_init()
## @brief Setup the environment for parallel computing.
## @details This functions is implicitly called when the module is
## sourced, it sets up the environment for parallel computing from the
## HPC scheduling environment of the process, if available (Slurm, PBS
## and LoadLeveler supported). If no scheduling environment is
## available, the environmental variable $NPTOTAL is used as number of
## desired parallel tasks. If set in input, the variable $NPIO
## indicates the number of tasks dedicated to I/O, not involved in
## Cartesian computation. The parcomp_computetopo() function is
## implicitly called by this function with the proper mumber of
## computational tasks.  On output, the variables `$NPX`, `$NPY`,
## `$NPIO` (if not set on input) and `$NP` (total number of parallel
## tasks including I/O tasks) are set.
parcomp_init() {
    [ -n "$NPIO" ] || NPIO=0
    if [ -n "$SLURM_NTASKS" ]; then # slurm
	parcomp_computetopo $(($SLURM_NTASKS - $NPIO))
    elif [ -n "$PBS_NODEFILE" -a -f "$PBS_NODEFILE" ]; then # pbs
	parcomp_computetopo `wc -l "$PBS_NODEFILE"`
    elif [ -n "$LOADL_TOTAL_TASKS" ]; then # LoadLeveler
	parcomp_computetopo $(($LOADL_TOTAL_TASKS - $NPIO))
    elif [ -n "$NPTOTAL" ]; then # generic
	parcomp_computetopo $(($NPTOTAL - $NPIO))
    else
	parcomp_computetopo 1
    fi
    NP=$(($NPX*$NPY+$NPIO))
}

## @fn parcomp_computetopo()
## @brief Compute a 2-D processor topology from the total number of
## tasks.
## @details This function computes a reasonable 2-D task (processor)
## Cartesian topology for parallel computing given the total number of
## computational tasks. The topology is set in the `$NPX` `$NPY`
## environment variables.
## @param $1 the number of computational tasks requested
parcomp_computetopo() {
    if [ "$1" -ge 384 ]; then
	NPX=16
	NPY=24
    elif [ "$1" -ge 352 ]; then
	NPX=16
	NPY=22
    elif [ "$1" -ge 320 ]; then
	NPX=16
	NPY=20
    elif [ "$1" -ge 288 ]; then
	NPX=16
	NPY=18
    elif [ "$1" -ge 256 ]; then
	NPX=16
	NPY=16
    elif [ "$1" -ge 204 ]; then
	NPX=14
	NPY=16
    elif [ "$1" -ge 192 ]; then
	NPX=6
	NPY=32
    elif [ "$1" -ge 180 ]; then
	NPX=10
	NPY=18
    elif [ "$1" -ge 160 ]; then
	NPX=10
	NPY=16
    elif [ "$1" -ge 144 ]; then
	NPX=8
	NPY=18
    elif [ "$1" -ge 136 ]; then
	NPX=8
	NPY=17
    elif [ "$1" -ge 128 ]; then
	NPX=8
	NPY=16
    elif [ "$1" -ge 108 ]; then
	NPX=6
	NPY=18
    elif [ "$1" -ge 96 ]; then
	NPX=6
	NPY=16
    elif [ "$1" -ge 72 ]; then
	NPX=4
	NPY=18
    elif [ "$1" -ge 68 ]; then
	NPX=4
	NPY=17
    elif [ "$1" -ge 64 ]; then
	NPX=4
	NPY=16
    elif [ "$1" -ge 60 ]; then
	NPX=6
	NPY=10
    elif [ "$1" -ge 56 ]; then
	NPX=4
	NPY=14
    elif [ "$1" -ge 54 ]; then
	NPX=6
	NPY=9
    elif [ "$1" -ge 50 ]; then
	NPX=5
	NPY=10
    elif [ "$1" -ge 48 ]; then
	NPX=4
	NPY=12
    elif [ "$1" -ge 44 ]; then
	NPX=4
	NPY=11
    elif [ "$1" -ge 42 ]; then
	NPX=3
	NPY=14
    elif [ "$1" -ge 40 ]; then
	NPX=4
	NPY=10
    elif [ "$1" -ge 36 ]; then
	NPX=4
	NPY=9
    elif [ "$1" -ge 32 ]; then
	NPX=2
	NPY=16
    elif [ "$1" -ge 30 ]; then
	NPX=3
	NPY=10
    elif [ "$1" -ge 28 ]; then
	NPX=4
	NPY=7
    elif [ "$1" -ge 24 ]; then
	NPX=3
	NPY=8
    elif [ "$1" -ge 21 ]; then
	NPX=3
	NPY=7
    elif [ "$1" -ge 20 ]; then
	NPX=4
	NPY=5
    elif [ "$1" -ge 18 ]; then
	NPX=3
	NPY=6
    elif [ "$1" -ge 16 ]; then
	NPX=4
	NPY=4
    elif [ "$1" -ge 12 ]; then
	NPX=3
	NPY=4
    elif [ "$1" -ge 9 ]; then
	NPX=3
	NPY=3
    elif [ "$1" -ge 8 ]; then
	NPX=2
	NPY=4
    elif [ "$1" -ge 4 ]; then
	NPX=2
	NPY=2
    elif [ "$1" -ge 2 ]; then
	NPX=1
	NPY=2
    else # troppo pochi
	NPX=1
	NPY=1
    fi
}

## @fn parcomp_mpirun()
## @brief Run a parallel MPI process starting the required number of tasks.
## @details This function runs a parallel MPI process starting the
## required number of tasks, in a scheduler-independent and MPI
## implementation-independent way (not yet implemented).
## @param $* additional arguments to mpirun, parallel executable and its optional arguments
parcomp_mpirun() {
# adapt to mpi/queuing system used
    mpirun -np $NP $@
}


## @fn get_job_status()
## @brief Get the status of a batch job
## @details This function queries the batch scheduler and prints on
## stdout the status of a batch job; it recognises slurm and pbs
## schedulers. The output is one letter (possibly scheduler dependent)
## indicating the job status, no output with error code 0 if the job
## does not exists or no output with error code 1 if the scheduler is
## not recognized.
## @param $1 the id of the job
get_job_status() {
    if type qstat >/dev/null 2>&1; then
	qstat -f $1 2>/dev/null |grep '^ *job_state *= *'|sed -e 's/^ *job_state *= *//g' || true
    elif type squeue >/dev/null 2>&1; then
	squeue -h --job $1 --format=%t 2>/dev/null || true
    else
# batch scheduling system not recognised
	return 1
    fi
}


## @fn cd_submit_dir()
## @brief Change working directory to submit directory.
## @details This function changes the current working directory to the
## directory from which a job was submitted to a batch scheduler;
## outside a batch environment it silently does nothing. It is useful
## to write portable scripts that can work both on the command line
## and under a batch scheduler.
cd_submit_dir() {
    if [ -n "$SLURM_SUBMIT_DIR" ]; then # slurm
	cd $SLURM_SUBMIT_DIR
    elif [ -n "$PBS_O_WORKDIR" ]; then # pbs
	cd $PBS_O_WORKDIR
    elif [ -n "$LOADL_STEP_INITDIR" ]; then # LoadLeveler, verify
	cd $LOADL_STEP_INITDIR
    fi # no scheduler, do nothing
}


# start exporting all assignments
set -a
# setup parallel computing environment
parcomp_init
# stop exporting all assignments
set +a
