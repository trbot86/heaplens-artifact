There are three main steps: modify target application source code to add logging (then compile & run the modified application), sample the output logs and put into sqlite database, and visualize the sampled allocations.

## Step 0: Build and lauch Docker image

Step 1 below relies on a specific version of clang and LLVM (version 14), which in turn requires Ubuntu 22 or higher, so it may be simpler to get things working inside a Docker container. To build and lauch a Docker image, do the following:

1. Navigate to the directory containing the Dockerfile

		cd docker/ubuntu_22_04

2. Run the script to build and launch the Docker image

		sudo ./build_image_and_lauch.sh --name sifter
		
3. Copy target application source code to Docker container

		sudo docker cp [target-application-directory] sifter:/root/sifter/

## Step 1: Modify target application

This step uses clang-tidy to add logging instructions to the target application.

1. Add desired allocation functions to the MATCH_FUNCTIONS macro in clang-tidy-standalone/misc/AllocationLoggingCheck.cpp

2. Write templated versions of any custom allocation functions (see templated malloc function in memhook/memhook_interface.h)

3. Run script to add logging information to memory allocations. If the target application is written in C++ (rather than C), use the -t flag.

		./sifter.sh [target-application-dir] [new-dir-name] -t --skip-refactor --build 'bear -- [make-command]'

This will generate a list of modifications in the file 'fixes.yaml'. If 'fixes.yaml' is empty following this step, then either the target application contains no dynamic memory allocations or something went wrong. This step should also produce a file called 'fielddump.txt' containing information about the fields of user-defined classes and structs.

If the target application is compiled by simply calling 'make', then you do not need to specify the build command.

Note: currently, you must use the --skip-refactor flag. Hypothetically, excluding the flag does the remaining refactoring in a single step, but this isn't working right now...

4. Add memhook directory to the include, library, and linker paths in your makefile. For example:

		CXXFLAGS += -I/root/sifter/memhook/
		LDFLAGS += -L/root/sifter/memhook/ -Wl,-rpath=/root/sifter/memhook/ -lmemhook -ldl

5. Include memhook_interface.h in all source files. To do this, run the following:

		./sifter.sh [new-dir-name] --includes-only

6. Run your target application. This will produce a few files: binary_dump.txt, fileset_dump.txt, and typeset_dump.txt.
## Step 2: Sample output logs

This step samples a set of memory pages from binary_dump.txt.

1. Run the sampling script as follows:

		./sifter.sh [new-dir-name] -d --sample [proportion-sampled] --pages-per-type [num-pages] --field-dump fielddump.txt

The argument provided to --sample is a real number between 0 and 1 that largely determines the size of the resulting database. A good rule of thumb is to aim for a database size of around 500MB or less (depending on the power of your machine). For example, if the size of binary_dump.txt is 5GB, then the proportion of events sampled should be around 0.1 or less.

With --pages-per-type you are specifying, for each type T, how many memory pages the sampler should pick containing at least one allocation of type T. By default this is 1, but you may want to increase this number if you are interested in seeing more pages containing underrepresented types. Note that picking a large number here will also increase the size of the resulting database.

This step should produce a file called 'allocs.sqlite' in the 'type_analysis' directory.

## Step 3: Visualization

This step allows you to visualize the database produced in the previous step. You will need node.js, Flask, and scikit-learn.

1. Start the Flask server in a separate terminal. This allows the web app to communicate with the python sampling script.

		cd sifter_vis_d3
		flask --app server run

2. Navigate to the visualization application directory, install node dependencies, and run the server.

		cd sifter_vis_d3/sifter
		npm install
		npm run dev

3. Copy 'allocs.sqlite' from the previous step into the 'sifter_vis_d3' directory.

4. Open 'localhost:3000' in your web browser. Note that it can take a few minutes to load a database in the visualization app. If it takes too long, you may want to choose a lower sampling proportion value in the sampling step.