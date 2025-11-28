# Installation

<h2>Installation</h2>

1. Install the package from `GitHub`.

   ```python
   pip install git+https://github.com/cjkpl/wagtail-cjk404.git
   ```

2. Add the application to the `INSTALLED_APPS` in the `settings.py` file.

    ```python
    INSTALLED_APPS = [
        "cjk404",
    ]
    ```

3. Add the `PageNotFoundRedirectMiddleware` middleware. You may also want to disable `Wagtail's` default `RedirectMiddleware`.

    ```python
    MIDDLEWARE = [
        'cjk404.middleware.PageNotFoundRedirectMiddleware',
        # "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    ]
    ```

<details>
<summary><h2>Installation (Development)</h2></summary>

If you want install a `Python` application in editable mode, you can use the editable mode provided by `pip`.

1. Clone the application's source code:

   ```python
   git clone https://github.com/cjkpl/wagtail-cjk404 .
   ```

2. Navigate to the root directory of the application's source code in the terminal or command prompt.

3. Install the application in editable mode.

   Use the pip install command with the `-e` or `--editable` flag followed by a period (`.`) to specify the current
   directory (where the application's `setup.py` file is located).

   ```python
   pip install -e .
   ```

   Replace the `.` with the path to the directory if you're running the command from a different location.

4. Add the application to the `INSTALLED_APPS` in the `settings.py` file.

   ```python
   INSTALLED_APPS = [
       "cjk404",
   ]
   ```

5. Add the `PageNotFoundRedirectMiddleware` middleware. You may also want to disable `Wagtail's` default `RedirectMiddleware`.

    ```python
    MIDDLEWARE = [
        'cjk404.middleware.PageNotFoundRedirectMiddleware',
        # "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    ]
    ```

</details>
