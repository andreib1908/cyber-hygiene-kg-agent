# dsaiproject

Check `.pre-commit-config.yaml`, `package.json`, `ruff.toml` and `requirements-dev` for the appropriate ruff, prettier and pre-commit versions.

Below are the steps to set up VS Code.

## 1. Installing UV

UV is a package manager that helps us get tools and set up PATH easily.

https://docs.astral.sh/uv/#installation

Open Windows PowerShell and run the following command (from the website):

`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Check if it was installed correctly in PowerShell:
`uv`

## 2. Installing Ruff

Ruff is a Python formatter. Get this for nice Python code (and minimal merge conflicts!).

In PowerShell, run:

`uv tool install ruff`

Check installation in PowerShell:

`ruff version`
-> Should see something like `ruff 0.13.3 (188c0dce2 2025-10-02)`

## 3. Installing Pre-commit

Pre-commit will run before each git commit. It will format the code and remove most errors automatically.

In PowerShell, run:

`uv tool install pre-commit`

**NOTE**:
After committing, if Pre-commit auto-fixes files, Git will ask you to stage and commit again. This is expected — just add the fixed files and commit once more.

## 4. PULL from Github

Now open VSCode and simply **pull** from **main**. The configuration files of note are:

- `.pre-commit-config.yaml`
- `package.json`
- `requirements-dev.txt`
- `ruff.toml`

## 5. Install requirements-dev.txt

Open a terminal in VSCode and type:

`pip install -r requirements-dev.txt`

## 6. Install Prettier

Prettier is a JavaScript formatter.

In a VSCode terminal run:

`npm install`

It will use the `package.json` dependencies.

## 7. Install Pre-commit Locally

In a VScode terminal run:

`pre-commit install`

## 8. VSCode Extensions

Get the following extensions from VSCode:

- Ruff
- Even Better TOML

## 9. Configure VSCode User Settings

In VSCode, press `CTRL + SHIFT + P` and type 'user' and select the first option `Preferences: Open User Preferences (JSON)`.

Paste the following code in the `settings.json` file that opened up:

```
{
    "[python]": {
            "editor.formatOnSave": true,
            "editor.defaultFormatter": "charliermarsh.ruff",
            "editor.codeActionsOnSave": {
                "source.fixAll": "explicit",
                "source.organizeImports": "explicit"
            }
    }
}
```

## 10. Check that the pre-commits work

Run in VSCode:
`pre-commit run --all-files`.

This will test if Ruff and Prettier work on your installation.
