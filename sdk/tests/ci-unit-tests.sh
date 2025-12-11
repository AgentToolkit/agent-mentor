#!/usr/bin/env bash

# copy the script logic from one of the sample apps that best resembles your app

# run the unit tests setup
# source $WORKSPACE/$PIPELINE_CONFIG_REPO_PATH/$CI_DIR/$APP_REPO_NAME/unit-tests-setup.sh
source "${COMMONS_PATH}/doi/doi-publish-testrecord.sh"

path="$(load_repo app-repo path)"
cd "$WORKSPACE/${path}" || exit 1



evidence_params=(
  --tool-type "unittest" \
  --evidence-type "com.ibm.unit_tests" \
  --asset-type "repo" \
  --asset-key "app-repo"
)

# TODO: check where unit-tests.log gets printed to. Probably ${WORKSPACE}/${path}/unit-tests.log and not the current:
output="$WORKSPACE/unit-tests.log"
reusedEvidenceLog="$(mktemp)"
status_file="$(mktemp)"
url=$(get_env repository)
if (check-evidence-for-reuse "${evidence_params[@]}" --output-path "${reusedEvidenceLog}" > "${status_file}"); then
  status=$(cat "$status_file")
  exit_code=0
  doi-publish --evidence-file "${reusedEvidenceLog}" --attachment-label "$output" --record-type "cradeploy" --url "$url" --attachment-output-path "$WORKSPACE/$output" || exit_code=$?
  if [ $exit_code == "0" ] && [ -s "$WORKSPACE/$output" ]; then
    echo "Saving results..."
    save_result test "$WORKSPACE/unit-tests.log"
    exit $exit_code
  fi
else
  # no evidence found for reuse, proceed with scan and collect-evidence
  echo "Pipeline environment:"
  echo "API KEY exists: $(get_env AZURE_OPENAI_API_KEY "" | wc -c) bytes"
  echo "ENDPOINT exists: $(get_env AZURE_OPENAI_ENDPOINT "" | wc -c) bytes"
  
  max_attempts=2
  attempt=1

  echo "API KEY exists: $(get_env ibmcloud-api-key "" | wc -c) bytes"
  echo "CIL5 ACCOUNT GUID exists: $(get_env cil5-account-guid "" | wc -c) bytes"
  ibmcloud login --apikey $(get_env ibmcloud-api-key "") -c $(get_env cil5-account-guid "") -r us-south -g SPS-for-agntanlytc
  ibmcloud cr login
  sed -i 's|ssh://git@github\.ibm\.com|https://${GIT_TOKEN}@github.ibm.com|g' requirements_dev.txt
  tail -1 requirements_dev.txt

  ############## Linting: Start ##############
  echo "Executing linting..."
  # set -x # Uncomment for debugging
  set-commit-status   --repository "$url"   --commit-sha "$COMMIT_SHA"   --state "pending"   --description "Linting step has started. Awaiting results."   --context "code-lint"
  echo $?

  docker run \
  -v "$WORKSPACE":"$WORKSPACE" \
  -w "${WORKSPACE}/${path}" \
  -e WORKSPACE="$WORKSPACE" \
  -e PYTHONPATH="${WORKSPACE}/${path}/src" \
  -e GIT_TOKEN=$(get_env git-token "") \
  us.icr.io/sps-agntanlytc/agntanlytc-ci-image \
  /bin/bash -c -x '\
    echo "GIT_TOKEN exists: ${GIT_TOKEN:+yes}" && \
    echo "WORKSPACE is: $WORKSPACE" && \
    echo "Alive!" > $WORKSPACE/lint.log && \
    tail -1 requirements_dev.txt && \
    envsubst --version && \
    cat requirements_dev.txt | envsubst > requirements_resolved.txt && \
    (uv pip install --system --no-cache-dir -r requirements_resolved.txt && rm requirements_resolved.txt && \
    echo "==== flake8 linter output:" && \
    flake8 .) >> $WORKSPACE/lint.log 2>&1; \
    exit_status=$?; \
    echo "Log file contents:"; \
    cat $WORKSPACE/lint.log; \
    ls -la $WORKSPACE/lint.log; \
    exit $exit_status'
  exit_code=$?

  echo ""
  echo "$WORKSPACE/lint.log:"
  cat "$WORKSPACE/lint.log"
  echo ""

  status="success"
  if [ $exit_code == "0" ]; then
    echo "Lint completed OK..."
  else
    echo "Error executing linter!!! Check linter output above"
    status="failure"
  fi
  set-commit-status   --repository "$url"   --commit-sha "$COMMIT_SHA"   --state "$status"   --description "Linting completed with $status."   --context "code-lint"
  ############## Linting: End ################

  echo "Executing unit-tests..."
  until [ $attempt -gt $max_attempts ]
  do
    echo "Attempt $attempt of $max_attempts"
    docker run \
    -v "$WORKSPACE":"$WORKSPACE" \
    -w "${WORKSPACE}/${path}" \
    -e WORKSPACE="$WORKSPACE" \
    -e PYTHONPATH="${WORKSPACE}/${path}/src" \
    -e AZURE_OPENAI_API_KEY=$(get_env AZURE_OPENAI_API_KEY "") \
    -e AZURE_OPENAI_ENDPOINT=$(get_env AZURE_OPENAI_ENDPOINT "") \
    -e WATSONX_URL=$(get_env WATSONX_URL "") \
    -e WATSONX_PROJECT_ID=$(get_env WATSONX_PROJECT_ID "") \
    -e WX_API_KEY=$(get_env WX_API_KEY "") \
    -e WATSONX_APIKEY=$(get_env WATSONX_APIKEY "") \
    -e WX_PROJECT_ID=$(get_env WX_PROJECT_ID "") \
    -e WX_URL=$(get_env WX_URL "") \
    -e GIT_TOKEN=$(get_env git-token "") \
    us.icr.io/sps-agntanlytc/agntanlytc-ci-image \
    /bin/bash -c -x '\
      echo "AZURE_OPENAI_API_KEY exists: ${AZURE_OPENAI_API_KEY:+yes}" && \
      echo "AZURE_OPENAI_ENDPOINT exists: ${AZURE_OPENAI_ENDPOINT:+yes}" && \
      echo "WATSONX_URL exists: ${WATSONX_URL:+yes}" && \
      echo "WATSONX_PROJECT_ID exists: ${WATSONX_PROJECT_ID:+yes}" && \
      echo "WX_API_KEY exists: ${WX_API_KEY:+yes}" && \
      echo "WATSONX_APIKEY exists: ${WATSONX_APIKEY:+yes}" && \
      echo "WX_PROJECT_ID exists: ${WX_PROJECT_ID:+yes}" && \
      echo "WX_URL exists: ${WX_URL:+yes}" && \
      echo "GIT_TOKEN exists: ${GIT_TOKEN:+yes}" && \
      echo "WORKSPACE is: $WORKSPACE" && \
      echo "Alive!" > $WORKSPACE/unit-tests.log && \
      tail -1 requirements_dev.txt && \
      envsubst --version && \
      cat requirements_dev.txt | envsubst > requirements_resolved.txt && \
      (uv pip install --system --no-cache-dir -r requirements_resolved.txt && rm requirements_resolved.txt && \
      python3 run_tests.py) >> $WORKSPACE/unit-tests.log 2>&1; \
      exit_status=$?; \
      echo "Log file contents:"; \
      cat $WORKSPACE/unit-tests.log; \
      ls -la $WORKSPACE/unit-tests.log; \
      exit $exit_status'
    exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "Tests passed on attempt $attempt"
        break
    fi
    echo "Test failed, retrying..."
    sleep 10
    ((attempt++))
  done
  
    

  # PYTHONPATH=src python3 run_tests.py >"$WORKSPACE/unit-tests.log" 2>&1
  # exit_code=$?
  
  status="success"
  if [ $exit_code == "0" ]; then
    echo "Unit tests completed OK..."
  else
    echo "Error executing unit tests !!!"
    status="failure"
  fi
  echo ""
  echo "$WORKSPACE/unit-tests.log:"
  cat "$WORKSPACE/unit-tests.log"
  echo ""

  collect-evidence \
    --tool-type "unittest" \
    --status "$status" \
    --evidence-type "com.ibm.unit_tests" \
    --asset-type "repo" \
    --asset-key "app-repo" \
    --attachment "$WORKSPACE/unit-tests.log"

  echo "Saving results..."
  save_result test "$WORKSPACE/unit-tests.log"

  exit $exit_code
fi
