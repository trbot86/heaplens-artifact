'use client';
import { Avatar, CssBaseline, List, ListItem, ListItemAvatar, ListItemText, ListItemButton, TextField, Paper } from '@mui/material';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import './page.scss';
import { useEffect, useState } from 'react';
import { EditNote, KeyboardArrowRight, Storage } from '@mui/icons-material';
import Box from '@mui/material/Box';
import Markdown from 'react-markdown';

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
    return data;
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
    const [notesDisplayed, setNotesDisplayed] = useState<string | null>(null);
    const [notesDisplayedFname, setNotesDisplayedFname] = useState<string | null>(null);

    useEffect(() => {
        getDBFiles()
            .then((resp) => setFiles(resp));
        getLogFiles()
            .then((resp) => {
                resp.json().then((logs) => setLogFiles(new Set(logs.map((fname: string) => fname.slice(0, -10) /* remove _save.json */ + '.sqlite'))))
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
                                                            logFiles.has(file) &&
                                                            <ListItemAvatar
                                                                className={'showNotesButton' + (notesDisplayedFname == file ? ' selectedFile' : '')}
                                                                onClick={() => {
                                                                    if (notesDisplayedFname != file) {
                                                                        getNotesForFile(file).then((resp) => resp.json())
                                                                            .then((notes) => {
                                                                                console.log('Here are notes:');
                                                                                console.log(notes);
                                                                                setNotesDisplayed(notes);
                                                                                setNotesDisplayedFname(file);
                                                                            });
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
                    <Markdown>{notesDisplayed}</Markdown>
                </Paper>
                }
            </Box>
        </ThemeProvider>
    );
}
