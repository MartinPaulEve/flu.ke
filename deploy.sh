#!/bin/bash
git pull --no-edit
git push
ssh personal ./deploy-fluke.sh

