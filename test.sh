#!/bin/bash
export PYTHONPATH=$PYTHONPATH:`pwd`/src

cd tests

echo "Running master api tests"
python -m master_tests.master_api_tests

echo "Running master command tests"
python -m master_tests.master_command_tests

echo "Running master communicator tests"
python -m master_tests.master_communicator_tests

echo "Running outputs tests"
python -m master_tests.outputs_tests

echo "Running inputs tests"
python -m master_tests.inputs_tests

echo "Running passthrough tests"
python -m master_tests.passthrough_tests

echo "Running thermostats tests"
python -m master_tests.thermostats_tests

echo "Running eeprom controller tests"
python -m master_tests.eeprom_controller_tests

echo "Running users tests"
python -m gateway_tests.users_tests

echo "Running scheduling tests"
python -m gateway_tests.scheduling_tests

echo "Running power controller tests"
python -m power_tests.power_controller_tests

echo "Running power communicator tests"
python -m power_tests.power_communicator_tests

echo "Running time keeper tests"
python -m power_tests.time_keeper_tests

echo "Running plugin base tests"
python -m plugins_tests.base_tests

echo "Running plugin interfaces tests"
python -m plugins_tests.interfaces_tests
