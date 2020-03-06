#include <iostream>
#include <fstream>
#include <sqlite3.h>

using namespace std;

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

void readfromfile(const char *filename, sqlite3 *db)
{
    char* zErrMsg = 0;

    ifstream myfile(filename);

    int counter = 0;

    string file;
    string type;
    string line;
    string timestamp;
    string size;
    string address;
    string typeofop;
    string data;

    if (myfile.is_open())
    {
        while (getline(myfile, data))
        {
            switch (counter)
            {
                // insert FILE
            case 0:
                file = data;
                break;
                // insert TYPE
            case 1:
                type = data;
                break;
                // insert LINE
            case 2:
                // line = atoi(data.c_str());
                line = data;
                break;
                // insert TIMESTAMP
            case 3:
                // timestamp = atoi(data.c_str());
                timestamp = data;
                break;
                // insert SIZE
            case 4:
                // size = atoi(data.c_str());
                size = data;
                break;
                // insert ADDRESS
            case 5:
                // address = strtol( data.c_str(), NULL, 16 );
                address = data;
                break;
                // insert TYPEOFOP
            case 6: {
                // typeofop = atoi(data.c_str());
                typeofop = data;

                string command = "INSERT INTO ALLOCS VALUES ('" + file + "'" + ","  + type + "," + line + "," + timestamp + "," + size + "," + address + ", '" + typeofop + ");";
                // cout << "inserting\n";
                sqlite3_exec(db, command.c_str(), callback, 0, &zErrMsg);
                break;
            }
            default:
                break;
            }
            counter++;
            counter = counter %7;
        }
    }
}

int main(int argc, char **argv)
{
    sqlite3 *db;
    char *zErrMsg = 0;
    int rc;

    if (argc != 3)
    {
        fprintf(stderr, "Usage: %s DATABASE SQL-STATEMENT\n", argv[0]);
        return 1;
    }

    rc = sqlite3_open(argv[1], &db);
    if (rc)
    {
        fprintf(stderr, "can't open database\n");
        return 1;
    }

    string create = "CREATE TABLE ALLOCS("  \
      "FILE CHAR(50)    NOT NULL," \
      "TYPE CHAR(100)," \
      "LINE INT    NOT NULL," \
      "TIMESTAMP INT PRIMARY KEY    NOT NULL," \
      "SIZE INT," \
      "ADDRESS INT    NOT NULL," \
      "isNew INT NOT NULL"
      ");";

    string gettablename = "SELECT table_name FROM information_schema.tables;";

    string importdb = ".import ../prac/setbench-master/microbench/info_t_dump.txt";

    rc = sqlite3_exec(db, create.c_str(), callback, 0, &zErrMsg);
    rc = sqlite3_exec(db, importdb.c_str(), callback, 0, &zErrMsg);
    if (rc != SQLITE_OK)
    {
        fprintf(stderr, "SQL error: %s\n", zErrMsg);
        // sqlite3_free(zErrMsg);
    }
    
    string dbname = "../prac/setbench-master/microbench/info_t_dump.txt";

    // readfromfile(dbname.c_str(), db);

    sqlite3_close(db);
    return 0;
}