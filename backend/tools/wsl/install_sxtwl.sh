set -e
rm -rf ~/sxvenv
pip3 install --user -q virtualenv 2>&1 | tail -2
~/.local/bin/virtualenv -q ~/sxvenv
~/sxvenv/bin/pip install sxtwl==2.0.7 2>&1 | tail -3
~/sxvenv/bin/pip show sxtwl | head -8
~/sxvenv/bin/python -c "import sxtwl;print([a for a in dir(sxtwl) if not a.startswith('_')])"
