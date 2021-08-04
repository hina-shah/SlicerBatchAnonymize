cmake_minimum_required(VERSION 3.13.4)

project(DSCI_Anonymizer)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/DSCI_Anonymizer")
set(EXTENSION_CATEGORY "DSCI")
set(EXTENSION_CONTRIBUTORS "Hina Shah (UNC Chapel Hill)")
set(EXTENSION_DESCRIPTION "This is an example of a simple extension")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/DSCI_Anonymizer.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/DSCI_Anonymizer/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(DSCI_Anonymize)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
