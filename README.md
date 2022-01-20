# DSCI_Anonymizer
This project is in active development

This is a Slicer extension that provides a user friendly interface to anonymize a 'batch' of DICOM images. 
- Anonymization is done with the help of Slicer's DICOM database utilities and file conversions
- Multiple output formats are supported (nifti, gipl, and dicom series)
- A mapping file is saved along with the anonymized files
- Users can preview the crosswalk/mapping and change the target names of the files
- Can be setup as a standalong application

## Quick Start
- Install the extension from the Slicer's Extension Index
- Go to Modules -> DSCI -> DSCI_Anonymizer
- Point the Input Directory to your parent directory with the dicom images
- In the Outputs section, point to the location where anonymized files will be saved.
- Chose the output folder
- Options for anonymized image naming:
-- You can use UUIDs
-- Change the prefix of the file names
-- Change the file name completely within the crosswalk table itself

## Illustrations

![](Documentation/GUIPreview.png?width=200px)
![](Documentation/CrosswalkPreview.png?width=100px)
