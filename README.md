# Online Diff Helper

A single file, simple helper to show the difference between output of programs. (Also known as "对拍")

## Usage

Due to the use of `/tmp` and the default shell called by `subprocess`, the script only runs on linux.

```bash
pip3 install -r requirements.txt
flask run --host=0.0.0.0 --port=80
```

Then you can access <https://localhost:80/login/letmelogin> to get your access for the website.

## Features and Guidance

1. Access `/problems` to see the problem list.
2. Access `/problems/<problemName>` to create a new problem named as `<problemName>`.
3. Access `/problems/<problemName>/remove` to remove a existing problem.
4. Generator files: The codes in the `Code` text box will be compiled to a binary file, which is used to generate data for the program. The first line of its stdout will be treated as command line arguments. The rest of them will be the stdin for all the solvers.
5. Statics files: Files which will not be compiled immediately. There should be a `Makefile` in it. After uploading the solver zip, all the static files will be placed with files in the solver zip and `make` will be run. The `a.out` (if exists) will be treated as the solver binary. Therefore, do not use `-o` in the default option of `Makefile`.
6. Solver files: Files which will be compiled with static files after uploaded using `make` command. Uploaded codes will be wiped once the compilation in finished. No need to worry about leaking your codes to others.
7. After uploading multiple solvers, click `Run`.

## Statement

We are not responsible for any usage of this code violating the Honor Code in UMJI-SJTU.
