import './style.css';
import initDB from './dbloader.js';

/*  Following two lines prevent browser from loading file dropped outside drop 
    area (also fixes bug where browser sometimes tries to load file dropped
    inside drop area) */
window.addEventListener("dragover", e => e.preventDefault(), false);
window.addEventListener("drop", e => e.preventDefault(), false);
initDB();