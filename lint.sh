#!/bin/bash
cd python
pylint --rcfile=../openmotics.rc *.py bus gateway master plugins power
