import os
from typing_extensions import assert_type
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import DICOMLib.DICOMUtils as dutils
import DICOMScalarVolumePlugin
import SimpleITK as sitk
import sitkUtils
import numpy as np
from pathlib import Path
import csv
import uuid
import ScreenCapture
import timeit
#
# SlicerBatchAnonymize
#

class SlicerBatchAnonymize(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "SlicerBatchAnonymize"  # TODO: make this more human readable by adding spaces
    self.parent.categories = ["DSCI"]  # TODO: set categories (folders where the module shows up in the module selector)
    self.parent.dependencies = []  # TODO: add here list of module names that this module requires
    self.parent.contributors = ["Hina Shah (UNC Chapel Hill.)"]  # TODO: replace with "Firstname Lastname (Organization)"
    # TODO: update with short description of the module and a link to online module documentation
    self.parent.helpText = "Helper tool for anonymizing multiple DICOM series/files.\n \
      In the 'Inputs' section point to the directory with the datasets \n \
      In the 'Outputs' section specify a prefix for the files, and the output format \n \
      The 'Preview Crosswalk' gives a preview of the dicom series and the target file names. \
      Users can change the file names to something else if so desired. "

    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = "This work was supported by the National Institutes of Dental and Craniofacial Research and Biomedical Imaging and Bioengineering of the National Institutes of Health under Award Number DE024450"

"""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#SlicerBatchAnonymize">module documentation</a>.
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

#
# SlicerBatchAnonymizeWidget
#
class SlicerBatchAnonymizeWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent=None):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.__init__(self, parent)
    VTKObservationMixin.__init__(self)  # needed for parameter node observation
    self.logic = None
    self._parameterNode = None
    self._updatingGUIFromParameterNode = False
    self.input_image_list = {}
    self.output_dir = None
    self.input_path = None
    self.isSingleModuleShown = False
    self.setParameterNode(None)

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/SlicerBatchAnonymize.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = SlicerBatchAnonymizeLogic()

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
    # (in the selected parameter node).
    self.ui.inputFormatComboBox.connect("currentIndexChanged(int)", self.onInputFormatChanged)
    self.ui.useUUIDCheckBox.connect("toggled(bool)", self.updateParameterNodeFromGUI)
    self.ui.inDirButton.connect('directoryChanged(QString)', self.onInputDirChanged)
    self.ui.outDirButton.connect('directoryChanged(QString)', self.onOutputDirChanged)
    self.ui.outputFormatComboBox.connect("currentIndexChanged(int)", self.updateParameterNodeFromGUI)
    self.ui.prefixLineEdit.connect("textChanged(QString)",  self.updateParameterNodeFromGUI)
    self.ui.crosswalkTableWidget.currentItemChanged.connect(self.onCrossWalkRowChanged)
    #self.ui.crosswalkTableWidget.itemChanged.connect(self.testSignal)
    self.ui.crosswalkTableWidget.itemPressed.connect(self.setManualEditOn)
    self.ui.crosswalkTableWidget.itemChanged.connect(self.testSignal)
    self.ui.progressBar.value = 0
    self.ui.progressLabel.text = "Nothing to do"
    self.manualEditOn = False
    # Buttons
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()
    mgr = slicer.app.layoutManager()
    if mgr is not None:
      mgr.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)

    #self.layoutWidget.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutSideBySideView)
    slicer.util.mainWindow().setWindowTitle("DSCI Anonymization tool")
    
    shortcut = qt.QShortcut(slicer.util.mainWindow())
    shortcut.setKey(qt.QKeySequence("Ctrl+Shift+b"))
    shortcut.connect('activated()', lambda: self.showSingleModule(toggle=True))
    self.showSingleModule(self.isSingleModuleShown)

  def setManualEditOn(self, item):
    self.manualEditOn = True

  def testSignal(self, item):
    if self.manualEditOn:
      row = item.row()
      col = item.column()
      for d in self.input_image_list:
        if self.input_image_list[d][0] == row:
          row_text = self.ui.crosswalkTableWidget.item(row, 0).text()
          if row_text != self.input_image_list[d][1]:
            self.input_image_list[d][1] = row_text
            self.input_image_list[d][2] = True
            self.updateParameterNodeFromGUI()
      self.manualEditOn = False

  def onCrossWalkRowChanged(self, current, previous):
    if previous==None:
      return
    prev_row = previous.row()
    for d in self.input_image_list:
      if self.input_image_list[d][0] == prev_row:
        # Get the new file name in column 0 for the previous row, compare and set
        prev_row_text = self.ui.crosswalkTableWidget.item(prev_row, 0).text()
        if prev_row_text != self.input_image_list[d][1]:
          self.input_image_list[d][1] = prev_row_text
          self.input_image_list[d][2] = True
          self.updateParameterNodeFromGUI()

  def onInputFormatChanged(self):
    dir_name = self.ui.inDirButton.directory
    print(dir_name)
    self.onInputDirChanged(dir_name)

  def onInputDirChanged(self, dir_name):
    self.input_path = Path(str(dir_name))
    if not self.input_path.exists():
      logging.error('The directory {} does not exist'.format(self.input_path))
      return
    # Get the list of images:
    input_image_list = []
    input_pattern = self.ui.inputFormatComboBox.currentText.split(',')
    for pattern in input_pattern:
      logging.info("Finding: " + pattern)
      input_image_list.extend( list(self.input_path.glob("**/" + pattern)))
    dir_set = set()
    if len(input_image_list) > 0:
      for im in input_image_list:
        dir_set.add(im.parent)
    self.input_image_list = {}
    if len(dir_set) > 0:
      # This would be the list of directories (i.e. one full scan image in one directory)
      for idx, d in enumerate(sorted(dir_set)):
        # third element keeps track of manual edits. False: auto, True is manual
        self.input_image_list[d] = [idx,"", False]
    self.updateParameterNodeFromGUI()

  def onOutputDirChanged(self, dir_name):
    output_dir = Path(str(dir_name))
    if not output_dir.exists():
      logging.error('The directory {} does not exist'.format(output_dir))
      return
    self.output_dir = output_dir
    self.updateParameterNodeFromGUI()

  def showSingleModule(self, singleModule=True, toggle=False):
      if toggle:
        singleModule = not self.isSingleModuleShown

      self.isSingleModuleShown = singleModule

      if singleModule:
        # We hide all toolbars, etc. which is inconvenient as a default startup setting,
        # therefore disable saving of window setup.
        settings = qt.QSettings()
        settings.setValue('MainWindow/RestoreGeometry', 'false')

      keepToolbars = [
        #slicer.util.findChild(slicer.util.mainWindow(), 'MainToolBar'),
        # slicer.util.findChild(slicer.util.mainWindow(), 'ViewToolBar'),
        # slicer.util.findChild(slicer.util.mainWindow(), 'ViewersToolBar')
         ]
      slicer.util.setToolbarsVisible(not singleModule, keepToolbars)
      slicer.util.setMenuBarsVisible(not singleModule)
      slicer.util.setApplicationLogoVisible(not singleModule)
      slicer.util.setModulePanelTitleVisible(not singleModule)
      slicer.util.setDataProbeVisible(not singleModule)

      if singleModule:
        slicer.util.setPythonConsoleVisible(self.developerMode)

  def cleanup(self):
    """
    Called when the application closes and the module widget is destroyed.
    """
    self.removeObservers()

  def enter(self):
    """
    Called each time the user opens this module.
    """
    # Make sure parameter node exists and observed
    self.initializeParameterNode()

  def exit(self):
    """
    Called each time the user opens a different module.
    """
    # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
    self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

  def onSceneStartClose(self, caller, event):
    """
    Called just before the scene is closed.
    """
    # Parameter node will be reset, do not use it anymore
    self.input_image_list={}
    self.setParameterNode(None)

  def onSceneEndClose(self, caller, event):
    """
    Called just after the scene is closed.
    """
    # If this module is shown while the scene is closed then recreate a new parameter node immediately
    if self.parent.isEntered:
      self.initializeParameterNode()

  def initializeParameterNode(self):
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.
    self.setParameterNode(self.logic.getParameterNode())

  def setParameterNode(self, inputParameterNode):
    """
    Set and observe parameter node.
    Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
    """
    if inputParameterNode:
      self.logic.setDefaultParameters(inputParameterNode)
    # Unobserve previously selected parameter node and add an observer to the newly selected.
    # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
    # those are reflected immediately in the GUI.
    if self._parameterNode is not None:
      self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    self._parameterNode = inputParameterNode
    if self._parameterNode is not None:
      self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
    # Initial GUI update
    self.updateGUIFromParameterNode()

  def updateGUIFromParameterNode(self, caller=None, event=None):
    """
    This method is called whenever parameter node is changed.
    The module GUI is updated to show the current state of the parameter node.
    """
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    # Update node selectors and sliders
    #print(self._parameterNode.GetParameter("InListDetailsString"))
    self.ui.inDetailsLabel.setText(self._parameterNode.GetParameter("InListDetailsString"))
    self.ui.useUUIDCheckBox.checked = (self._parameterNode.GetParameter("UseUUID") == "true")
    self.ui.defaceChecBox.checked = (self._parameterNode.GetParameter("Deface") == "true")
    self.ui.prefixLineEdit.setText(self._parameterNode.GetParameter("OutputPrefix"))
    self.ui.prefixLineEdit.setEnabled(not self.ui.useUUIDCheckBox.checked)
    # self.ui.progressLabel.setText(self._parameterNode.GetParameter("ProgressText"))
    # self.ui.progressBar.setValue(int(self._parameterNode.GetParameter("ProgressValue")))
    
    formatText = self._parameterNode.GetParameter("OutputFormat")
    outIndex = max(0, self.ui.outputFormatComboBox.findText(formatText))
    self.ui.outputFormatComboBox.setCurrentIndex(outIndex)

    formatText = self._parameterNode.GetParameter("InputFormat")
    outIndex = max(0, self.ui.inputFormatComboBox.findText(formatText))
    self.ui.inputFormatComboBox.setCurrentIndex(outIndex)

    prefix_condition = (not self.ui.useUUIDCheckBox.checked and len(self.ui.prefixLineEdit.text) > 0) or self.ui.useUUIDCheckBox.checked
    self.ui.applyButton.setEnabled(len(self.input_image_list) > 0 and \
                                  self.output_dir is not None and \
                                  self.output_dir.exists() and \
                                  prefix_condition)
    #Update the crosswalk dict and text here
    self.ui.crosswalkTableWidget.setRowCount(len(self.input_image_list))
    self.ui.crosswalkTableWidget.setHorizontalHeaderLabels(["Output file name", "Target for input"])
    self.ui.crosswalkTableWidget.horizontalHeader().setVisible(True)
    if len(self.input_image_list) > 0:
      for k in self.input_image_list:
        entry =  self.input_image_list[k]
        index = entry[0]
        if entry[2]:
          # Filename was edited manually.
          filename = entry[1]
        elif (self._parameterNode.GetParameter("UseUUID") == "true"):
          filename = str(uuid.uuid4())
        else:
          filename = (self._parameterNode.GetParameter("OutputPrefix")+ "_%04d"%(index+1))
        self.input_image_list[k][1]=filename
        newItem = qt.QTableWidgetItem(filename)
        newItem.setToolTip(filename)
        self.ui.crosswalkTableWidget.setItem(index, 0, newItem)

        try:
          rel_path = Path(k).relative_to(self._parameterNode.GetParameter("InputDirectory"))
          # print(k)
          # print(self._parameterNode.GetParameter("InputDirectory"))
          newItem1 = qt.QTableWidgetItem(rel_path)
        except ValueError as e:
          newItem1 = qt.QTableWidgetItem(k)
        newItem1.setToolTip(str(k))
        newItem1.setFlags(newItem1.flags() & ~qt.Qt.ItemIsEditable)
        self.ui.crosswalkTableWidget.setItem(index, 1, newItem1)
    self.ui.crosswalkTableWidget.resizeColumnToContents(1)

    # All the GUI updates are done
    self._updatingGUIFromParameterNode = False

  def updateParameterNodeFromGUI(self, caller=None, event=None):
    """
    This method is called when the user makes any change in the GUI.
    The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
    """
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch
    self._parameterNode.SetParameter("InListDetailsString", "Will anonymize: " + str(len(self.input_image_list)) + " images")
    self._parameterNode.SetParameter("UseUUID", "true" if self.ui.useUUIDCheckBox.checked else "false")
    self._parameterNode.SetParameter("Deface", "true" if self.ui.defaceChecBox.checked else "false")
    self._parameterNode.SetParameter("OutputPrefix", self.ui.prefixLineEdit.text)
    self._parameterNode.SetParameter("InputDirectory", self.ui.inDirButton.directory)
    self._parameterNode.SetParameter("OutputDirectory", self.ui.outDirButton.text)
    self._parameterNode.SetParameter("InputFormat", self.ui.inputFormatComboBox.currentText)
    self._parameterNode.SetParameter("OutputFormat", self.ui.outputFormatComboBox.currentText)
    # self._parameterNode.SetParameter("ProgressText", self.ui.progressLabel.text)
    # self._parameterNode.SetParameter("ProgressValue", str(self.ui.progressBar.value))
    self._parameterNode.EndModify(wasModified)
    self.updateGUIFromParameterNode()

  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    try:
      # Compute output
      deface_method = None
      if self.ui.defaceChecBox.checked:
        if "CBCT" in self.ui.defaceImageTypeComboBox.currentText:
          deface_method = "AMASSS"

      self.logic.process(self.input_image_list, self.output_dir, self.ui.outputFormatComboBox.currentText, deface_method, self.ui.progressBar, self.ui.progressLabel)
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()

#
# SlicerBatchAnonymizeLogic
#

class SlicerBatchAnonymizeLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self):
    """
    Called when the logic class is instantiated. Can be used for initializing member variables.
    """
    ScriptedLoadableModuleLogic.__init__(self)
    self.process_cont = False

  def setDefaultParameters(self, parameterNode):
    """
    Initialize parameter node with default settings.
    """
    parameterNode.SetParameter("UseUUID", "false")
    parameterNode.SetParameter("OutputPrefix", "File")
    parameterNode.SetParameter("InListDetailsString", "No directory selected")
    parameterNode.SetParameter("InputDirectory", "")
    parameterNode.SetParameter("OutputDirectory", "")
    parameterNode.SetParameter("InputFormat", "*.dcm,*.dicom,*.DICOM,*.DCM")
    parameterNode.SetParameter("OutputFormat", ".nii.gz")
    # parameterNode.SetParameter("ProgressText", "Nothing")
    # parameterNode.SetParameter("ProgressValue", "0")

  def reportProgress(self, msg, percentage, progressbar, progressmsg):
    # Abort download if cancel is clicked in progress bar
    # if slicer.progressWindow.wasCanceled:
    #   raise Exception("process aborted")
    # # Update progress window
    # slicer.progressWindow.show()
    # slicer.progressWindow.activateWindow()
    # slicer.progressWindow.setValue(int(percentage))
    # slicer.progressWindow.setLabelText(msg)
    # # Process events to allow screen to refresh
    # slicer.app.processEvents()
    if progressbar is not None:
      if percentage == 0:
        progressbar.reset()
      progressbar.value = percentage
      progressbar.update()
    if progressmsg is not None:
      progressmsg.text = msg
      progressmsg.update()
  
  def runDefacing(self, img_path, seg_path, debug = True):
    """
    :param img_path :  original input image
    :param seg_path : path where skin segmentation lives
    """

    # Read the original image
    try:
      volume = slicer.util.loadVolume(img_path)
    except Exception as e:
      logging.error(f"Error reading the input volume {img_path}, \n {e}")
      return False
    # Read the segmentation in as a labelmap

    try:
      segmentation_path = list(Path(seg_path).glob("*SKIN-Seg_Pred.nii.gz"))[0]
      segmentation = slicer.util.loadVolume(str(segmentation_path))
    except Exception as e:
      logging.error(f"Error reading the SKIN Segmentation from directory {seg_path}, \n {e}")
      return False

    # Run closing on labelmap using original pixel spacing
    ### Get pixel spacing from the oriignal volume:
    print(f"Spacing for the input volume is: {volume.GetSpacing()}")
    targetClosingDistance = 20 #mm
    xClosingRadius = int(targetClosingDistance / volume.GetSpacing()[0])
    yClosingRadius = int(targetClosingDistance / volume.GetSpacing()[1])
    zClosingRadius = int(targetClosingDistance / volume.GetSpacing()[2])
    print(f"Will close by: {[xClosingRadius, yClosingRadius, zClosingRadius]}")
    # Pull image from Slicer:
    sitkInputImage = sitkUtils.PullVolumeFromSlicer(segmentation)
    filter = sitk.BinaryMorphologicalClosingImageFilter()
    filter.SetKernelRadius([xClosingRadius, yClosingRadius, zClosingRadius])
    filter.SafeBorderOn()
    closedImage = filter.Execute(sitkInputImage)
    
    # Run dilation step
    print("Running Extra Dilation")
    filter = sitk.BinaryDilateImageFilter()
    filter.SetKernelRadius([3,3,3])
    filter.SetForegroundValue(1)
    filter.SetBoundaryToForeground(False)
    closedDilatedImage = filter.Execute(closedImage)

    if debug:
      closedDilatedSlicerImage = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "SegmentationClosedDilated")
      sitkUtils.PushVolumeToSlicer(closedDilatedImage, closedDilatedSlicerImage, className="vtkMRMLLabelMapVolumeNode")

    # Run Masking
    # Masking
    print("Running masking")
    voxels = slicer.util.arrayFromVolume(volume)
    mask = sitk.GetArrayFromImage(closedDilatedImage) #slicer.util.arrayFromVolume(closedDilatedSlicerImage)
    maskedVoxels = np.copy(voxels)  # we don't want to modify the original volume
    maskedVoxels[mask==0] = 0

    # Write masked volume to volume node and show it
    if debug:
      maskedVolumeNode = slicer.modules.volumes.logic().CloneVolume(volume, "MaskedImage")
      slicer.util.updateVolumeFromArray(maskedVolumeNode, maskedVoxels)

    # Subtraction from original volume
    
    # `a` and `b` are numpy arrays,
    # they can be combined using any numpy array operations
    # to produce the result array `c`
    defaced = voxels - maskedVoxels
    if debug:
      defacedNode = slicer.modules.volumes.logic().CloneVolume(volume, "Defaced")
      slicer.util.updateVolumeFromArray(defacedNode, defaced)

    # Threshold
    defaced[ defaced < 0 ] = 0
    defacedThreshNode = slicer.modules.volumes.logic().CloneVolume(volume, "DefacedThresh")
    slicer.util.updateVolumeFromArray(defacedThreshNode, defaced)
    defacedImgPath = str(img_path).replace(".nii.gz", "_defaced.nii.gz")
    slicer.util.saveNode(defacedThreshNode, str(defacedImgPath))

    # Render
    
    mgr = slicer.app.layoutManager()
    if mgr is not None:
      mgr.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)

    print("Showing volume rendering of node " + defacedThreshNode.GetName())
    volRenLogic = slicer.modules.volumerendering.logic()
    displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(defacedThreshNode)
    displayNode.SetAutoScalarRange(True)
    displayNode.SetFollowVolumeDisplayNode(True)
    
    displayNode.SetVisibility(True)

    #Set background to black (required for transparent background)
    view = slicer.app.layoutManager().threeDWidget(0).threeDView()
    view.mrmlViewNode().SetBackgroundColor(1,1,1)
    view.mrmlViewNode().SetBackgroundColor2(1,1,1)
    view.resetFocalPoint()
    view.mrmlViewNode().SetAxisLabelsVisible(False)
    view.mrmlViewNode().SetBoxVisible(False)
    view.forceRender()
    numberOfScreenshots = 4
    #axisIndex = [0, 2, 4, 1, 3, 5]  # order of views in the gallery image
    axisIndex = [3, 0, 1, 4]
    cap = ScreenCapture.ScreenCaptureLogic()
    for screenshotIndex in range(numberOfScreenshots):
        view.rotateToViewAxis(axisIndex[screenshotIndex])
        slicer.util.forceRenderAllViews()
        outputFilename = str(img_path).replace(".nii.gz", "_def_screenshot_" + str(screenshotIndex) + ".png")
        cap.captureImageFromView(view, outputFilename)
    
      # # Capture RGBA image
      # renderWindow = view.renderWindow()
      # renderWindow.SetAlphaBitPlanes(1)
      # wti = vtk.vtkWindowToImageFilter()
      # wti.SetInputBufferTypeToRGBA()
      # wti.SetInput(renderWindow)
      # writer = vtk.vtkPNGWriter()
      # writer.SetFileName(str(img_path).replace(".nii.gz", "_def_screenshot.png"))
      # writer.SetInputConnection(wti.GetOutputPort())
      # writer.Write()

      # for i in range(6):
      #   view.yaw()
      # wti = vtk.vtkWindowToImageFilter()
      # wti.SetInputBufferTypeToRGBA()
      # wti.SetInput(renderWindow)
      # writer = vtk.vtkPNGWriter()
      # writer.SetFileName(str(img_path).replace(".nii.gz", "_def_screenshot_1.png"))
      # writer.SetInputConnection(wti.GetOutputPort())
      # writer.Write()

    # Do cleanup
    slicer.mrmlScene.RemoveNode(volume)
    slicer.mrmlScene.RemoveNode(segmentation)
    slicer.mrmlScene.RemoveNode(defacedThreshNode)

    if debug:
      slicer.mrmlScene.RemoveNode(closedDilatedSlicerImage)
      slicer.mrmlScene.RemoveNode(maskedVolumeNode)
      slicer.mrmlScene.RemoveNode(defacedNode)

      
    return True

    
  def process(self, input_image_list, output_dir, out_format, deface_method, progressbar=None, progressmsg=None):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """
    self.process_cont = True
    if input_image_list is None or output_dir is None or out_format is None:
      return

    if len(input_image_list) == 0 or not output_dir.exists():
      raise ValueError("Input or output specified is invalid")

    
    import time
    startTime = time.time()
    logging.info('Processing started')

    crosswalk = []
    error_files = []
    # read the input directory for dicoms,
    slicerdb = slicer.dicomDatabase
    if not slicerdb.isOpen:
        # Get the directory path for the Slicer database, and try to open it.
        slicer.dicomDatabaseDirectorySettingsKey = 'DatabaseDirectory_'+ctk.ctkDICOMDatabase().schemaVersion()
        settings = qt.QSettings()
        databaseDirectory = settings.value(slicer.dicomDatabaseDirectorySettingsKey)
        if not databaseDirectory:
          documentsLocation = qt.QStandardPaths.DocumentsLocation
          documents = qt.QStandardPaths.writableLocation(documentsLocation)
          databaseDirectory = os.path.join(documents, slicer.app.applicationName+"DICOMDatabase")
          settings.setValue(slicer.dicomDatabaseDirectorySettingsKey, databaseDirectory)
        if not os.path.exists(databaseDirectory):
            print("Creating the database directory")
            os.mkdir(databaseDirectory)
        databaseFileName = databaseDirectory + "/ctkDICOM.sql"
        print("Will try to open at: {}".format(databaseFileName))
        slicer.dicomDatabase.openDatabase(databaseFileName)
        slicerdb = slicer.dicomDatabase
        if not slicerdb.isOpen:
          raise OSError('Slicer DICOM database cannot be accessed/generated. Tried at: {}'.format(databaseDirectory))
        else:
          logging.info("Generated Slicer DICOM Database at: {}".format(databaseDirectory))

    stage = "Importing DICOM Data to database"
    self.reportProgress(stage, 0, progressbar, progressmsg)
    #progress = qt.QProgressDialog("Importing DICOM Data to database", "Abort Load", 0, len(input_image_list))
    #progress.reset()
    #progress.setWindowModality(qt.Qt.WindowModal)
    for idx, imgpath in enumerate(list(input_image_list.keys())):
      self.reportProgress(stage, (idx+1)*100.0/len(input_image_list), progressbar, progressmsg)
      if self.process_cont == False:
        self.reportProgress("Process canceled", 0, progressbar, progressmsg)
        break      
      #progress.setValue(idx+1)
      # if progress.wasCanceled:
      #   break
      dutils.importDicom( imgpath, slicerdb)
    # progress.setValue(len(input_image_list))
    # progress.reset()
    print("Done importing to Slicer DICOM Database")
    #del progress
    self.reportProgress("Done importing to Slicer DICOM Database", 0, progressbar, progressmsg)
    slicer.app.processEvents()
    # # progress.setWindowModality(qt.Qt.WindowModal)
    stage = "Anonymizing and Exporting"
    self.reportProgress(stage, 0, progressbar, progressmsg)
    self.process_cont = True
    scalarVolumeReader = DICOMScalarVolumePlugin.DICOMScalarVolumePluginClass()
    slicer.app.processEvents()
    #slicer.progressWindow = slicer.util.createProgressDialog(parent=slicer.util.mainWindow(),windowTitle='Anonymizing and exporting')
    idx = 0
    time_keys = ["file_output", "anon_time"]
    if deface_method is not None:
      time_keys.extend(['seg_time', 'deface_time', 'deface_method'])
    time_rows = []
    try:
      for patient in slicerdb.patients():
        for study in slicerdb.studiesForPatient(patient):
          for series in slicerdb.seriesForStudy(study):
            time_row = {}
            if self.process_cont == False:
              raise Exception("User stopped processing")            
            files = slicerdb.filesForSeries(series)
            imgpath =  Path(files[0]).parent
            if imgpath in input_image_list:
              print("Will export this: " + str(imgpath))
              time_row['file_output'] = input_image_list[imgpath][1]
              anon_time_start = timeit.default_timer()
              self.reportProgress(stage + " : " + str(imgpath), (idx+1)*100.0/len(input_image_list), progressbar, progressmsg)
              slicer.app.processEvents()
              try:
                loadable = scalarVolumeReader.examineForImport([files])[0]
                image_node = scalarVolumeReader.load(loadable)
                if image_node.GetImageData().GetDimensions()[2] == 1:
                  logging.warning("Image has only one slice, ignoring")
                  slicer.mrmlScene.RemoveNode(image_node)
                  continue
                if deface_method is not None:
                  (output_dir / "Defacing").mkdir(parents=True, exist_ok=True)
                  out_path = output_dir / ("Defacing/" + input_image_list[imgpath][1] + ".nii.gz")
                  slicer.util.saveNode(image_node, str(out_path))
                  if deface_method not in slicer.util.moduleNames():
                    logging.warning("Required module " + deface_method + " not installed. Please install the corresponding extension, and rerun")
                    continue
                  if deface_method == "AMASSS":
                    documentsLocation = qt.QStandardPaths.DocumentsLocation
                    documents = qt.QStandardPaths.writableLocation(documentsLocation)
                    modelsPath =  os.path.join(documents, "FULL_FACE_MODELS")
                    tempPath = qt.QStandardPaths.TempLocation
                    tempLoc = qt.QStandardPaths.writableLocation(tempPath)
                    print(str(out_path))
                    print(str(output_dir/"Defacing"))
                    parameters = {'inputVolume': str(out_path), 'modelDirectory': modelsPath, 'highDefinition': False, 'skullStructure': "SKIN", 'merge': ['MERGE'], 'genVtk': True, 'save_in_folder': True, 'output_folder': str(output_dir/"Defacing"), 'precision': 50, 'vtk_smooth': 5, 'prediction_ID': 'Pred', 'gpu_usage': 1, 'cpu_usage': 1, 'temp_fold': tempLoc}
                    print(parameters)
                    seg_time_start = timeit.default_timer()
                    slicer.cli.run(slicer.modules.amasss_cli, None, parameters, wait_for_completion=True, update_display=False)
                    seg_time_end = timeit.default_timer()
                    time_row['seg_time'] = seg_time_end - seg_time_start
                    time_row['deface_method'] = deface_method
                    deface_time_start = timeit.default_timer()
                    self.runDefacing(str(out_path), str(out_path).replace(".nii.gz", "_SegOut"), debug=False)
                    deface_time_end = timeit.default_timer()
                    time_row['deface_time'] = deface_time_end - deface_time_start
                if out_format == ".dcm":
                  output_folder = output_dir / input_image_list[imgpath][1]
                  output_folder.mkdir(parents=True, exist_ok=True)
                  # Create patient and study and put the volume under the study
                  shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
                  patientItemID = shNode.CreateSubjectItem(shNode.GetSceneItemID(), input_image_list[imgpath][1])
                  studyItemID = shNode.CreateStudyItem(patientItemID, input_image_list[imgpath][1]+'_Study')
                  volumeShItemID = shNode.GetItemByDataNode(image_node)
                  shNode.SetItemParent(volumeShItemID, studyItemID)
                  exporter = DICOMScalarVolumePlugin.DICOMScalarVolumePluginClass()
                  exportables = exporter.examineForExport(volumeShItemID)
                  if len(exportables) == 0:
                    logging.error("Cannot export this image (either 1 image or no image in the series)")
                    slicer.mrmlScene.RemoveNode(image_node)
                    continue
                  for exp in exportables:
                    exp.directory = output_folder
                  exporter.export(exportables)
                  slicer.mrmlScene.RemoveNode(shNode)
                  out_path = output_folder / ('ScalarVolume_' + str(exportables[0].subjectHierarchyItemID))
                else:
                  filename = input_image_list[imgpath][1] + out_format
                  out_path = output_dir / filename
                  slicer.util.saveNode(image_node, str(out_path))
                anon_time_end = timeit.default_timer()
                time_row['anon_time'] = anon_time_end - anon_time_start
                time_rows.append(time_row)
              except Exception as e:
                logging.error("Error reading/writing file: {} \n {}".format(imgpath, e))
                if image_node is not None:
                  slicer.mrmlScene.RemoveNode(image_node)
                error_files.append(imgpath)
              else:
                slicer.mrmlScene.RemoveNode(image_node)
                crosswalk.append( {"input": imgpath, "output" : out_path})
              idx+=1
    except Exception as e:
      self.reportProgress("Process canceled", 0, progressbar, progressmsg)
      logging.error("Export aborted: {}".format(e))
    #slicer.progressWindow.close()

    if len(crosswalk) > 0:
      try:
        with open(output_dir/"crosswalk.csv", "w", encoding="utf-8") as f:
          w = csv.DictWriter(f, crosswalk[0].keys())
          w.writeheader()
          w.writerows(crosswalk)
      except Exception as e:
        logging.error("Failed to write the crosswalk file")
        logging.error(e)
        slicer.util.errorDisplay("Failed to write the crosswalk file")
    if len(time_rows) > 0:
      try:
        with open(output_dir/"timings.csv", "w", encoding="utf-8") as f:
          w = csv.DictWriter(f, time_rows[0].keys())
          w.writeheader()
          w.writerows(time_rows)
      except Exception as e:
        logging.error("Failed to write the Timing file")
        logging.error(e)
        slicer.util.errorDisplay("Failed to write the Timing file")
    if len(error_files) > 0:
      try:
        with open(output_dir / "files_not_converted.txt", "w") as f:
          for e in error_files:
            f.write(str(e)+"\n")
      except IOError:
        logging.error("Failed to write the list of failed files")
        slicer.util.errorDisplay("Failed to write the list of failed files")
    stopTime = time.time()
    logging.info('Processing completed in {0:.2f} seconds'.format(stopTime-startTime))

    # for idx, imgpath in enumerate(input_image_list):
    #   progress.setValue(idx)
    #   if progress.wasCanceled:
    #     break
    #   try:
    #     image_node = slicer.util.loadVolume(str(imgpath), {'singleFile':True})
    #     if useUUID:
    #       filename = str(uuid.uuid4()) + ".nrrd"
    #     else:
    #       filename = (prefix+ "_%04d"%idx + ".nrrd")
    #     out_path = output_dir / filename
    #     slicer.util.saveNode(image_node, str(out_path))
    #   except Exception as e:
    #     logging.error("Error reading/writing file: {}".format(imgpath))
    #     if image_node is not None:
    #       slicer.mrmlScene.RemoveNode(image_node)
    #     error_files.append(imgpath)
    #   else:
    #     slicer.mrmlScene.RemoveNode(image_node)
    #     crosswalk.append( {"input": imgpath, "output" : out_path})
    # progress.setValue(len(input_image_list))

#
# SlicerBatchAnonymizeTest
#

class SlicerBatchAnonymizeTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear()

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_SlicerBatchAnonymize1()

  def test_SlicerBatchAnonymize1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")

    # Get/create input data

    # Test the module logic

    logic = SlicerBatchAnonymizeLogic()

    # Test algorithm with non-inverted threshold
    logic.process(None, None, None, None, None)
    print("Running defacing")
    did_good = logic.runDefacing("/Users/hinashah/Downloads/MG_test_scan.nii.gz", "/Users/hinashah/Downloads/MG_test_scan_SegOut")
    self.assertTrue(did_good)

    self.delayDisplay('Test passed')
 