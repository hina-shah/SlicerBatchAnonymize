import os
import unittest
import logging
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
import DICOMLib.DICOMUtils as dutils
import DICOMScalarVolumePlugin

from pathlib import Path
import csv
import uuid

#
# DSCI_Anonymize
#

class DSCI_Anonymize(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "DSCI_Anonymize"  # TODO: make this more human readable by adding spaces
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
    self.parent.acknowledgementText = ""

"""
This is an example of scripted loadable module bundled in an extension.
See more information in <a href="https://github.com/organization/projectname#DSCI_Anonymize">module documentation</a>.
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

#
# DSCI_AnonymizeWidget
#
class DSCI_AnonymizeWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
    self.setParameterNode(None)

  def setup(self):
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/DSCI_Anonymize.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = DSCI_AnonymizeLogic()

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
    self.manualEditOn = False
    # Buttons
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()
    slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)
    #self.layoutWidget.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutSideBySideView)
    self.isSingleModuleShown = False
    slicer.util.mainWindow().setWindowTitle("DSCI Anonymization tool")
    self.showSingleModule(True)
    shortcut = qt.QShortcut(slicer.util.mainWindow())
    shortcut.setKey(qt.QKeySequence("Ctrl+Shift+b"))
    shortcut.connect('activated()', lambda: self.showSingleModule(toggle=True))

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
    print(input_pattern)
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
    print(self._parameterNode.GetParameter("InListDetailsString"))
    self.ui.inDetailsLabel.setText(self._parameterNode.GetParameter("InListDetailsString"))
    self.ui.useUUIDCheckBox.checked = (self._parameterNode.GetParameter("UseUUID") == "true")
    self.ui.prefixLineEdit.setText(self._parameterNode.GetParameter("OutputPrefix"))
    self.ui.prefixLineEdit.setEnabled(not self.ui.useUUIDCheckBox.checked)
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
          filename = (self._parameterNode.GetParameter("OutputPrefix")+ "_%04d"%index)
        self.input_image_list[k][1]=filename
        newItem = qt.QTableWidgetItem(filename)
        newItem.setToolTip(filename)
        self.ui.crosswalkTableWidget.setItem(index, 0, newItem)

        try:
          rel_path = Path(k).relative_to(self._parameterNode.GetParameter("InputDirectory"))
          print(k)
          print(self._parameterNode.GetParameter("InputDirectory"))
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
    self._parameterNode.SetParameter("OutputPrefix", self.ui.prefixLineEdit.text)
    self._parameterNode.SetParameter("InputDirectory", self.ui.inDirButton.directory)
    self._parameterNode.SetParameter("OutputDirectory", self.ui.outDirButton.text)
    self._parameterNode.SetParameter("InputFormat", self.ui.inputFormatComboBox.currentText)
    self._parameterNode.SetParameter("OutputFormat", self.ui.outputFormatComboBox.currentText)
    self._parameterNode.EndModify(wasModified)
    self.updateGUIFromParameterNode()

  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    try:
      # Compute output
      self.logic.process(self.input_image_list, self.output_dir, self.ui.outputFormatComboBox.currentText)
    except Exception as e:
      slicer.util.errorDisplay("Failed to compute results: "+str(e))
      import traceback
      traceback.print_exc()

#
# DSCI_AnonymizeLogic
#

class DSCI_AnonymizeLogic(ScriptedLoadableModuleLogic):
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

  def reportProgress(self, msg, percentage):
    # Abort download if cancel is clicked in progress bar
    if slicer.progressWindow.wasCanceled:
      raise Exception("process aborted")
    # Update progress window
    slicer.progressWindow.show()
    slicer.progressWindow.activateWindow()
    slicer.progressWindow.setValue(int(percentage))
    slicer.progressWindow.setLabelText(msg)
    # Process events to allow screen to refresh
    slicer.app.processEvents()

  def process(self, input_image_list, output_dir, out_format):
    """
    Run the processing algorithm.
    Can be used without GUI widget.
    :param inputVolume: volume to be thresholded
    :param outputVolume: thresholding result
    :param imageThreshold: values above/below this threshold will be set to 0
    :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
    :param showResult: show output volume in slice viewers
    """

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
        raise OSError('Slicer DICOM module or database cannot be accessed')

    progress = qt.QProgressDialog("Importing DICOM Data to database", "Abort Load", 0, len(input_image_list))
    progress.reset()
    #progress.setWindowModality(qt.Qt.WindowModal)
    for idx, imgpath in enumerate(list(input_image_list.keys())):
      progress.setValue(idx+1)
      if progress.wasCanceled:
        break
      dutils.importDicom( imgpath, slicerdb)
    progress.setValue(len(input_image_list))
    progress.reset()
    print("Done importing to Slicer DICOM Database")
    del progress

    # # progress.setWindowModality(qt.Qt.WindowModal)
    scalarVolumeReader = DICOMScalarVolumePlugin.DICOMScalarVolumePluginClass()
    slicer.progressWindow = slicer.util.createProgressDialog(parent=slicer.util.mainWindow(),windowTitle='Anonymizing and exporting',autoClose=True)
    idx = 0
    try:
      for patient in slicerdb.patients():
        for study in slicerdb.studiesForPatient(patient):
          for series in slicerdb.seriesForStudy(study):
            self.reportProgress("Anonymizing and Exporting", (idx+1)*100.0/len(input_image_list))
            files = slicerdb.filesForSeries(series)
            imgpath =  Path(files[0]).parent
            if imgpath in input_image_list:
              print("Will export this: " + str(imgpath))
              try:
                loadable = scalarVolumeReader.examineForImport([files])[0]
                image_node = scalarVolumeReader.load(loadable)
                if image_node.GetImageData().GetDimensions()[2] == 1:
                  logging.warning("Image has only one slice, ignoring")
                  slicer.mrmlScene.RemoveNode(image_node)
                  continue
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
              except Exception as e:
                logging.error("Error reading/writing file: {}".format(imgpath))
                if image_node is not None:
                  slicer.mrmlScene.RemoveNode(image_node)
                error_files.append(imgpath)
              else:
                slicer.mrmlScene.RemoveNode(image_node)
                crosswalk.append( {"input": imgpath, "output" : out_path})
              idx+=1
    except Exception as e:
      logging.error("Export aborted: {}".format(e))
    slicer.progressWindow.close()

    if len(crosswalk) > 0:
      try:
        with open(output_dir/"crosswalk.csv", "w") as f:
          w = csv.DictWriter(f, crosswalk[0].keys())
          w.writeheader()
          w.writerows(crosswalk)
      except Exception as e:
        logging.error("Failed to write the crosswalk file")
        slicer.util.errorDisplay("Failed to write the crosswalk file", parent=self.parent)
    if len(error_files) > 0:
      try:
        with open(output_dir / "files_not_converted.txt", "w") as f:
          for e in error_files:
            f.write(e+"\n")
      except IOError:
        logging.error("Failed to write the list of failed files")
        slicer.util.errorDisplay("Failed to write the list of failed files", parent=self.parent)
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
# DSCI_AnonymizeTest
#

class DSCI_AnonymizeTest(ScriptedLoadableModuleTest):
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
    self.test_DSCI_Anonymize1()

  def test_DSCI_Anonymize1(self):
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

    logic = DSCI_AnonymizeLogic()

    # Test algorithm with non-inverted threshold
    logic.process(None, None)

    self.delayDisplay('Test passed')
 