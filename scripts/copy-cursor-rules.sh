#!/bin/bash

# Script to sync files from coralogix/ai-coding-rules repository's llm-tracekit folder
# to the local root directory using SSH
#
# Usage:
#   ./sync-ai-coding-rules.sh
#
# Environment Variables:
#   AI_CODING_RULES_BRANCH - Branch to sync from (default: master)
#
# Prerequisites:
#   - SSH key configured for GitHub access

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REPO_SSH="git@github.com:coralogix/ai-coding-rules.git"
SOURCE_FOLDER="llm-tracekit"
BRANCH="${AI_CODING_RULES_BRANCH:-master}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
TEMP_DIR=$(mktemp -d)

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI Coding Rules Sync Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Source: ${CYAN}$REPO_SSH (branch: $BRANCH, folder: $SOURCE_FOLDER)${NC}"
echo -e "Target: ${CYAN}$ROOT_DIR${NC}"
echo ""

echo -e "${YELLOW}Cloning repository using SSH...${NC}"
echo ""

# Clone the repository with sparse checkout to only get the llm-tracekit folder
cd "$TEMP_DIR"

# Initialize a new git repo
git init -q

# Add the remote
git remote add origin "$REPO_SSH"

# Enable sparse checkout
git sparse-checkout init --cone

# Set the folder to checkout
git sparse-checkout set "$SOURCE_FOLDER"

# Fetch and checkout only the specified folder
if ! git fetch --depth=1 origin "$BRANCH" 2>&1; then
    echo -e "${RED}Error: Failed to fetch from repository.${NC}"
    echo -e "${RED}Please ensure:${NC}"
    echo -e "${RED}  1. You have SSH access to the repository${NC}"
    echo -e "${RED}  2. Your SSH key is added to ssh-agent (ssh-add)${NC}"
    echo -e "${RED}  3. The branch '$BRANCH' exists${NC}"
    exit 1
fi

git checkout FETCH_HEAD -q

# Check if the source folder exists
if [ ! -d "$SOURCE_FOLDER" ]; then
    echo -e "${RED}Error: Folder '$SOURCE_FOLDER' not found in the repository${NC}"
    exit 1
fi

# Find all files in the source folder
cd "$SOURCE_FOLDER"

# Arrays to track files
declare -a FILES_TO_COPY=()
declare -a DUPLICATE_FILES=()
declare -a NEW_FILES=()

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Files found in remote repository:${NC}"
echo -e "${BLUE}========================================${NC}"

# Find all files recursively
while IFS= read -r -d '' file; do
    relative_path="${file#./}"
    
    echo -e "  📄 ${CYAN}$relative_path${NC}"
    
    local_file="$ROOT_DIR/$relative_path"
    
    if [ -f "$local_file" ]; then
        DUPLICATE_FILES+=("$relative_path")
    else
        NEW_FILES+=("$relative_path")
    fi
    
    FILES_TO_COPY+=("$relative_path")
done < <(find . -type f -print0)

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Summary:${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "  Total files found: ${GREEN}${#FILES_TO_COPY[@]}${NC}"
echo -e "  New files: ${GREEN}${#NEW_FILES[@]}${NC}"
echo -e "  Existing files (will be overwritten): ${YELLOW}${#DUPLICATE_FILES[@]}${NC}"
echo ""

# Show duplicate files
if [ ${#DUPLICATE_FILES[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  The following files already exist and will be OVERWRITTEN:${NC}"
    for file in "${DUPLICATE_FILES[@]}"; do
        echo -e "  ${YELLOW}↻ $file${NC}"
    done
    echo ""
fi

# Show new files
if [ ${#NEW_FILES[@]} -gt 0 ]; then
    echo -e "${GREEN}✨ New files to be created:${NC}"
    for file in "${NEW_FILES[@]}"; do
        echo -e "  ${GREEN}+ $file${NC}"
    done
    echo ""
fi

echo -e "${BLUE}Copying files...${NC}"

# Copy each file
for relative_path in "${FILES_TO_COPY[@]}"; do
    local_file="$ROOT_DIR/$relative_path"
    local_dir="$(dirname "$local_file")"
    source_file="$TEMP_DIR/$SOURCE_FOLDER/$relative_path"
    
    mkdir -p "$local_dir"
    
    if cp "$source_file" "$local_file"; then
        if [[ " ${DUPLICATE_FILES[*]} " =~ " ${relative_path} " ]]; then
            echo -e "  ${YELLOW}↻ Overwritten: $relative_path${NC}"
        else
            echo -e "  ${GREEN}+ Created: $relative_path${NC}"
        fi
    else
        echo -e "  ${RED}✗ Failed: $relative_path${NC}"
    fi
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Sync completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
