cmake_minimum_required(VERSION 3.13.4)

project(SlicerBatchAnonymize)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/hina-shah/SlicerBatchAnonymize")
set(EXTENSION_CATEGORY "DSCI")
set(EXTENSION_CONTRIBUTORS "Hina Shah (UNC Chapel Hill), Juan Carlos Prieto (UNC, Chapel Hill)")
set(EXTENSION_DESCRIPTION "SlicerBatchAnonymize is a Slicer extension that provides a user friendly interface to anonymize a 'batch' of DICOM images.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/hina-shah/SlicerBatchAnonymize/main/SlicerBatchAnonymize.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/hina-shah/SlicerBatchAnonymize/main/Documentation/GUIPreview.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(SlicerBatchAnonymize)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
