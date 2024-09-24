'use client';
import { Avatar, CssBaseline, List, ListItem, ListItemAvatar, ListItemText, ListItemButton, TextField } from '@mui/material';
import { createTheme, Theme, ThemeProvider } from '@mui/material/styles';
import './page.scss';
import { useEffect, useState } from 'react';
import { Storage } from '@mui/icons-material';
import Box from '@mui/material/Box';

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

    useEffect(() => {
        async function getData() {
            const resp = await fetch('http://localhost:5000/get-fnames');
            const files = await resp.json();
            setFiles(files);
        }
        getData();
    }, []);

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
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
                                                            <ListItemAvatar>
                                                                <Avatar>
                                                                    <Storage />
                                                                </Avatar>
                                                            </ListItemAvatar>
                                                            <ListItemText
                                                                primary={file} />
                                                        </ListItemButton>
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
        </ThemeProvider>
    );
}
