# Restoration Guide

This guide explains how to restore the full 4GB project environment from the 15MB source code available in this repository.

## 1. Node.js (Bridge Server & UI)

### Bridge Server
In the root directory, run:
```bash
npm install
```
This restores the `node_modules` folder (Express, CORS, etc.).

### Frontend UI
In the `lecture_analysis/ui` directory, run:
```bash
cd lecture_analysis/ui
npm install
cd ../..
```
This restores the Svelte/Vite/Tailwind environment.

## 2. Python Environments

### Main Environment
1. Create a virtual environment: `python -m venv lecture_analysis/venv`
2. Activate it: `source lecture_analysis/venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`

### Enhanced Environment
1. Create a second virtual environment: `python -m venv lecture_analysis/venv_vf2`
2. Activate it: `source lecture_analysis/venv_vf2/bin/activate`
3. Install dependencies: `pip install -r requirements_vf2.txt`

## 3. Temporary Files
Folders like `lecture_analysis/temp/` and `lecture_analysis/_TRASH/` are automatically created by the bridge server when needed. You don't need to restore them manually.

## 4. Launch Commands

Use the root launchers:

```bash
./audit.command
./lab.command
```

---
**Note:** The 4GB size is mostly due to downloaded Python libraries (PyTorch, librosa, etc.) in the `venv` folders. The source code itself remains lightweight and portable.
