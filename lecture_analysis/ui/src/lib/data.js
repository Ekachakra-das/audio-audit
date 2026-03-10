import data1 from '../../../analysis_folder1.json';
import data2 from '../../../analysis_folder2.json';
import globalData from '../../../global_conflicts.json';

// Explicitly export to ensure Vite bundles them
export const database = {
    folder1: data1,
    folder2: data2,
    global: globalData
};
