Prism: a light BEAM disassembler
================================

Install instructions
--------------------

Use *pip* to install this tool, preferrably in a virtual environment:

```
$ git clone https://github.com/quarkslab/erlang-prism.git
$ cd erlang-prism
$ pip install .
```

How to use Prism
----------------

*Prism* can disassemble any BEAM or EZ (BEAM archive) file using the following options:

```
$ erlang-prism -o my_output_dir -f my_example_file.beam
```

This command will disassemble `my_example_file.beam` in the output directory `my_output_dir`.

The `-s` option can be used for batch processing:

```
$ erlang-prism -o my_batch_output -s ./beam-files
```

In this case, *prism* will look for any BEAM or EZ file present in the provided directory and its subdirectories, disassemble them and store the disassembled files in the specified output directory `my_batch_output`.

Syntax highlighting
-------------------

A [VIM syntax file is provided](vim-syntax/beamc.vim) and can be used to highlight the
disassembled files, saved with the `.beamc` extension.