#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sqlite3.h>

#include "optionparser.h"

using namespace std;

enum optionIndex
{
    UNKNOWN,
    HELP,
    FILENAME,
    LISTTYPES
};
enum optionType
{
    CORE,
    META
};

struct Arg : public option::Arg
{
    static void printError(const char *msg1, const option::Option &opt, const char *msg2)
    {
        fprintf(stderr, "%s", msg1);
        fwrite(opt.name, opt.namelen, 1, stderr);
        fprintf(stderr, "%s", msg2);
    }

    static option::ArgStatus Filename(const option::Option &option, bool msg)
    {
        if (option.arg != 0)
        {
            // cout << option.arg << endl;
            return option::ARG_OK;
        }
        else
            return option::ARG_ILLEGAL;

        // if (msg) printError("Option '", option, "' requires an argument\n");
        // return option::ARG_ILLEGAL;
    }
};

const option::Descriptor usage[] =
    {
        {UNKNOWN, 0, "", "", option::Arg::None, "USAGE: sifter [options]\n\n"},
        {HELP, 0, "", "help", option::Arg::None, "   --help  \tPrint usage and exit."},
        {FILENAME, CORE, "g", "file", Arg::Filename, "   --file={filepath} \tpath to db"},
        {LISTTYPES, 0, "l", "typelist", option::Arg::None, "   --typelist \tprints all types which are used in db"},
        {0, 0, 0, 0, 0, 0}};

static int callback(void *NotUsed, int argc, char **argv, char **azColName)
{
    int i;
    for (i = 0; i < argc; i++)
    {
        printf("%s = %s\n", azColName[i], argv[i] ? argv[i] : "NULL");
    }
    printf("\n");
    return 0;
}

int main(int argc, char **argv)
{
    argc -= (argc > 0);
    argv += (argc > 0); //skip program name argv[0] if present

    string line;
    const char *file;

    sqlite3 *db;
    char *zErrMsg = 0;
    int rc;

    option::Stats stats(usage, argc, argv);
    option::Option options[stats.options_max], buffer[stats.buffer_max];
    option::Parser parse(usage, argc, argv, options, buffer);

    if (parse.error())
    {
        cout << "parsing error\n";
        option::printUsage(std::cout, usage);
        return 1;
    }

    if (options[HELP] || argc == 0)
    {
        cout << "help/no arguments\n";
        option::printUsage(std::cout, usage);
    }

    if (options[FILENAME].count() == 1)
    {
        cout << "file option detected\n";
        file = options[FILENAME].first()->arg;
    }
    else
    {
        cout << options[FILENAME].count();
        option::printUsage(std::cout, usage);
        return 1;
    }

    rc = sqlite3_open(file, &db);
    if (rc)
    {
        fprintf(stderr, "can't open database\n");
        return 1;
    }

    if (options[LISTTYPES])
    {
        rc = sqlite3_exec(db, "select distinct type from allocs", callback, 0, &zErrMsg);
        if (rc != SQLITE_OK)
        {
            fprintf(stderr, "SQL error: %s\n", zErrMsg);
            // sqlite3_free(zErrMsg);
        }
    }

    sqlite3_close(db);
    return 0;
}
