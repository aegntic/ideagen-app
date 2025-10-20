#!/bin/bash
# Create all directories for the Idea Engine App

# Workflow directories
mkdir -p workflows/01-idea-generation
mkdir -p workflows/02-validation
mkdir -p workflows/03-selection
mkdir -p workflows/04-project-init
mkdir -p workflows/05-website-builder
mkdir -p workflows/06-social-automation
mkdir -p workflows/07-analytics
mkdir -p workflows/08-orchestrator
mkdir -p workflows/shared

# Database directories
mkdir -p database/migrations

# Config directory
mkdir -p config

# Documentation directory
mkdir -p docs

echo "All directories created successfully!"
