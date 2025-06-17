'use client';
import { Avatar, CssBaseline, List, ListItem, ListItemAvatar, ListItemText, ListItemButton, TextField, Paper } from '@mui/material';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import './page.scss';
import { useEffect, useState } from 'react';
import { EditNote, KeyboardArrowRight, Storage } from '@mui/icons-material';
import Box from '@mui/material/Box';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function saveFileNameToDBFileName(sfn: string) {
    return sfn.slice(0, -10) /* remove _save.json */ + '.sqlite';
}

async function getDBFiles() {
    const resp = await fetch('http://localhost:5000/get-fnames');
    const files = await resp.json();
    return files;
}

async function getLogFiles() {
    const data = await fetch(`http://localhost:5000/log-data/get-files`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    return data;
}

export async function getNotesForFile(fname: string) {
    const data = await fetch(`http://localhost:5000/log-data/get-notes/${fname}`, {
        method: 'GET',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
    });
    const json = await data.json();
    return [fname, json];
}

export const theme: Theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: '#e0e0e0',
            contrastText: '#e9e7e5',
        },
        secondary: {
            main: '#bea7da',
        },
        background: {
            default: '#282828',
            paper: '#212121',
        },
        success: {
            main: '#42c947',
        },
    },
});

export default function FileSelect() {
    const [files, setFiles] = useState([]);
    const [filterText, setFilterText] = useState('');
    const [logFiles, setLogFiles] = useState<Set<string>>(new Set());
    const [logNotes, setLogNotes] = useState<{[a: string]: string}>({});
    const [notesDisplayed, setNotesDisplayed] = useState<string | null>(null);
    const [notesDisplayedFname, setNotesDisplayedFname] = useState<string | null>(null);

    useEffect(() => {
        getDBFiles()
            .then((resp) => setFiles(resp));
        getLogFiles()
            .then((resp) => {
                resp.json().then((logs) => {
                    setLogFiles(new Set(logs.map((fname: string) => saveFileNameToDBFileName(fname))));
                    Promise.all(logs.map((fname: string) => {
                        return getNotesForFile(saveFileNameToDBFileName(fname));
                    })).then((fileNotes: [string, string][]) => {
                        console.log("fileNotes:");
                        console.log(fileNotes);
                        const newLogNotes: {[a: string]: string} = {};
                        fileNotes.forEach((entry: [string, string]) => {
                            if (entry[1] !== "")
                                newLogNotes[entry[0]] = entry[1];
                        });
                        console.log("newLogNotes:");
                        console.log(newLogNotes);
                        setLogNotes(newLogNotes);
                    });
                })
            });
    }, []);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Box
                id='fileSelectPageContainer'
                className={notesDisplayed == null ? '' : 'notesExpanded'} >
                <Box
                    id='fileSelectBox'
                    sx={{
                        bgcolor: 'background.paper'
                    }} >
                    <div id='fileListDiv' >
                        <nav
                            id='fileListNav' 
                            aria-label='file select list' >
                            <List>
                                {
                                    files.filter((file: string) => file.includes(filterText))
                                        .map((file) => <ListItem
                                                            key={file}
                                                            disablePadding >
                                                            <ListItemButton
                                                                component='a'
                                                                href={`/vispanels?fname=${file}`} >
                                                                {/* <ListItemAvatar>
                                                                    <Avatar>
                                                                        <Storage />
                                                                    </Avatar>
                                                                </ListItemAvatar> */}
                                                                <ListItemText
                                                                    primary={file} />
                                                            </ListItemButton>
                                                            {
                                                            (file in logNotes) &&
                                                            <ListItemAvatar
                                                                className={'showNotesButton' + (notesDisplayedFname == file ? ' selectedFile' : '')}
                                                                onClick={() => {
                                                                    if (notesDisplayedFname != file) {
                                                                        setNotesDisplayed(logNotes[file]);
                                                                        setNotesDisplayedFname(file);
                                                                    }
                                                                }} >
                                                                <Avatar>
                                                                    <EditNote />
                                                                </Avatar>
                                                            </ListItemAvatar>
                                                            }
                                                            {
                                                            notesDisplayedFname == file &&
                                                            <KeyboardArrowRight />
                                                            }
                                                        </ListItem>)
                                }
                            </List>
                        </nav>
                    </div>
                    <TextField 
                        id='fileFilter'
                        label='Filter files'
                        variant='filled'
                        size='medium'
                        fullWidth
                        maxRows={1}
                        onChange={(e) => setFilterText(e.target.value)} />
                </Box>
                {
                notesDisplayed != null &&
                <Paper
                    id='notesDisplayedContainer'
                    elevation={3} >
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]} >
                        {notesDisplayed}
                    </ReactMarkdown>
                </Paper>
                }
            </Box>
        </ThemeProvider>
    );
}
