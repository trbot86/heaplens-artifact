# HeapLENS: Heap Layout Evaluation & Navigation Suite

**ACM ATC 2026 artifact (paper 483): start with [artifact/README.md](artifact/README.md).**
It contains the container quick start, experiment-to-paper map, guided example,
optional LLM workflow, and explicit verification status. The older developer
instructions below are retained for reference; use the artifact entry point for evaluation.

There are three main steps: modify target application source code to add logging (then compile & run the modified application), sample the output logs and put into sqlite database, and visualize the sampled allocations.

## Step 0: Build and launch Docker image

Step 1 below relies on a specific version of clang and LLVM (version 14), which in turn requires Ubuntu 22 or higher, so it may be simpler to get things working inside a Docker container. To build and launch a Docker image, do the following:

1. Navigate to the directory containing the Dockerfile

		cd docker/ubuntu_22_04

2. Run the script to build and launch the Docker image

		sudo ./build_image_and_launch.sh --name sifter
		
3. Copy target application source code to Docker container

		sudo docker cp [target-application-directory] sifter:/root/sifter/

## Step 1: Modify target application

This step uses clang-tidy to add logging instructions to the target application.

1. Add desired allocation functions to the MATCH_FUNCTIONS macro in clang-tidy-standalone/misc/AllocationLoggingCheck.cpp

2. Write templated versions of any custom allocation functions (see templated malloc function in memhook/memhook_interface.h)

3. Compute logging information for memory allocations. If the target application is written in C++ (rather than C), use the -t flag.

		./sifter.sh [target-application-dir] [new-dir-name] -t --skip-refactor --build 'bear -- [make-command]'

	This will generate a list of modifications in the file 'fixes.yaml'. If 'fixes.yaml' is empty following this step, then either the target application contains no dynamic memory allocations or something went wrong. This step should also produce a file called 'fielddump.txt' containing information about the fields of user-defined classes and structs.

	If the target application is compiled by simply calling 'make', then you do not need to specify the build command.

	Note: currently, you must use the --skip-refactor flag. Hypothetically, excluding the flag does the remaining refactoring in a single step, but this isn't working right now...

	To add custom logging, use the ```MEMHOOK_LOG_ALLOC``` and ```MEMHOOK_LOG_FREE``` macros in memhook_interface.h as follows:

		int* my_ints = (int*) malloc(10 * sizeof(int));
		MEMHOOK_LOG_ALLOC(my_ints, 10 * sizeof(int), typeid(int).name())
		...
		MEMHOOK_LOG_FREE(my_ints)
		custom_free_func(my_ints);

4. Add the logging information.

		cd [new-dir-name]
		clang-apply-replacements-14 ./

5. Add memhook directory to the include, library, and linker paths in your makefile. For example:

		CXXFLAGS += -I/root/sifter/memhook/
		LDFLAGS += -L/root/sifter/memhook/ -Wl,-rpath=/root/sifter/memhook/ -lmemhook -ldl

6. Include memhook_interface.h in all source files. To do this, run the following:

		./sifter.sh [new-dir-name] --includes-only

7. Compile your target application.

8. Run your target application. This will produce a few files: binary_dump.txt, fileset_dump.txt, and typeset_dump.txt.

## Step 2: Sample output logs

This step samples a set of memory pages from binary_dump.txt.

1. Run the sampling script as follows:

		./sifter.sh [new-dir-name] -d --sample [proportion-sampled] --pages-per-type [num-pages] --field-dump fielddump.txt

	The argument provided to --sample is a real number between 0 and 1 that largely determines the size of the resulting database. A good rule of thumb is to aim for a database size of around 500MB or less (depending on the power of your machine). For example, if the size of binary_dump.txt is 5GB, then the proportion of events sampled should be around 0.1 or less.

	With --pages-per-type you are specifying, for each type T, the minimum number of distinct memory pages containing an allocation of T to retain (or all such pages if fewer exist). By default this is 1, but you may want to increase this number to see more pages containing underrepresented types. Pages shared by several types count toward each type's minimum. Each selected page retains its complete event history. Larger minima can increase the database size. When invoking the converter directly, this option is named --num-pages-per-type.

	Sampling uses system entropy by default. Add --seed [integer] to repeat the initial page selection from the same log with the same converter build. The chosen seed is printed to stderr. This does not make the application's execution or the GUI's clustering deterministic.

	This step should produce a file called 'allocs.sqlite' in the 'type_analysis' directory.

## Step 3: Visualization

This step allows you to visualize the database produced in the previous step. You can either run the backend (with Flask) and frontend (with node.js) servers directly on your local machine, or you may build a virtual environment in Python using the included requirements.txt. This section will cover the latter approach.

**Shortcut:** `sifter_vis_d3/setup_and_launch.sh` automates all of steps 1-6 below (creating/reusing the virtual environment, installing the Python and node dependencies, and starting both servers) -- run it, then skip to step 7. Run it on your host machine, not inside the Docker container from Step 0, which doesn't include `sifter_vis_d3/` at all.

You will need Python 3 along with the venv module (which you should already have if you have Python >= 3.3).

1. Create a new Python virtual environment.

		python -m venv /path/to/venv

2. Activate the virtual environment.

	Using bash/zsh on POSIX systems:

		source /path/to/venv/bin/activate

	On Windows systems:

		path\to\venv\Scripts\activate.bat

	Note: to deactivate the virtual environment on POSIX, type `deactivate`. On Windows, run the script `path\to\venv\Scripts\deactivate.bat`.

3. In your virtual environment, install the modules in `requirements.txt`.

		cd sifter_vis_d3/server
		pip install -r requirements.txt

4. In the `server` directory, start the backend server.

		flask --app server run

5. In another terminal window, activate the Python virtual environment again (see step 2). Set up a node.js virtual environment using the `nodeenv` module.

		nodeenv --python-virtualenv --node 18.18.2


6. Navigate to the visualization application directory, install node dependencies, and run the server.

		cd sifter_vis_d3/sifter
		npm install
		npm run dev

7. Copy 'allocs.sqlite' from the previous step into the 'sifter_vis_d3' directory. If steps 1-2 ran inside the Docker container from Step 0 and this step is running on the host, the container's filesystem isn't bind-mounted, so use `docker cp` rather than a plain `cp`, e.g.:

		sudo docker cp sifter:/root/sifter/[new-dir-name]/type_analysis/allocs.sqlite sifter_vis_d3/

8. Open 'localhost:3000' in your web browser. Note that it can take a few minutes to load a database in the visualization app. If it takes too long, you may want to choose a lower sampling proportion value in the sampling step.

### Representative pages and text export

In **Settings → Sample settings**, set **Maximum pages** and **Maximum history
records**, then click **Resample**. The GUI defaults to at most 128 pages and
100,000 prepared history records, for either 4-KiB or huge-page views. A history
record describes an allocation lifetime or prepared fragment, not necessarily
an object live at the selected time. Both limits apply to the displayed pages;
they do not reduce the source database or bound database/cache preparation.

Selection prioritizes cluster coverage, then requested types, then large
within-cluster differences in history size, before adding page runs. The view
reports its selected counts and any omitted clusters/types. Perf-directed
pages remain mandatory: if they alone exceed a limit, the view warns about the
exception. Raise the limits to examine omitted layouts; lower them if the
selected histories make interaction slow. These are configurable working
limits, not a guarantee of responsiveness on every computer or trace.

Click **Export 5 snapshots** above the page view to save
`page_layout_snapshots.txt`. Loading or resampling no longer downloads a file
automatically. The file includes the selected pages, their cluster membership,
type/field metadata, and five evenly spaced snapshots from the earliest to
latest allocation timestamp in those pages. It includes both endpoints (and
repeated timestamps if the range is zero); an entirely empty history has one
empty snapshot. Export uses the selected pages' full prepared histories, not
the current slider position or visibility toggles.

Export shows progress and can be cancelled. Chrome/Edge on localhost or HTTPS
can write incrementally to a file chosen in the save dialog. Other browsers
download the completed file using a memory-limited fallback; exports above
64 MiB stop with an explanation instead of downloading truncated data. Use
direct file saving or select fewer pages for a larger export. Cancellation
aborts the write and does not intentionally save a partial export; a browser
may leave an empty placeholder for a newly chosen file.

The separate command-line pipeline, `bash artifact/run.sh export`, still
generates the packaged LLM workflow's raw/compact exports. Its snapshot count
and page-selection defaults are unchanged by the GUI's five-snapshot export.
