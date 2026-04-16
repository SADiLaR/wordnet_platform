#!/bin/bash

set -e

while getopts "d:r:h" opt; do                                                 
    case $opt in                                                              
        d) DJANGO_ROOT=$OPTARG ;;                                             
        r) REQUIREMENTS=$OPTARG ;;
        h)
            echo "Usage: prepcheck.sh [-d django_root] [-r requirements_file]"
            echo "  -d  Path to Django root (default: current directory)"     
            echo "  -r  Path to requirements file (default: requirements.txt)"
            exit 0                                                            
            ;;  
    esac                                                                      
done

DJANGO_ROOT=${DJANGO_ROOT:-.}                                                 
REQUIREMENTS=${REQUIREMENTS:-requirements.txt}

if git status --porcelain $DJANGO_ROOT/*/migrations/ 2>/dev/null | grep -q .; then
    echo "Uncommitted migration files detected."
    exit 1
fi

python $DJANGO_ROOT/manage.py test
python $DJANGO_ROOT/manage.py makemigrations --check --no-input
ruff check $DJANGO_ROOT
ruff format --diff $DJANGO_ROOT

SCRIPT_DIR=$(dirname "$0")
python "$SCRIPT_DIR/guess_req_mismatches.py" $DJANGO_ROOT $REQUIREMENTS

echo "Fetching latest master from origin..."
git fetch origin master 2>/dev/null

bad_commits=$(git log --pretty=format:%s origin/master..HEAD | grep -E 'fixup!|squash!|edit!|drop!' || true)
if [ -n "$bad_commits" ]; then
    echo ""
    echo "Found bad commits:"
    echo "$bad_commits"
    echo "Perform autosquash before merging"
    exit 1
else
    echo "No commits to autosquash"
fi
