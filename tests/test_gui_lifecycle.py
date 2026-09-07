"""Real Qt process exit is part of the regression contract."""
import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_studio_extract_repeat_error_cancel_and_close(tmp_path):
    script = textwrap.dedent('''
        import time
        from pathlib import Path
        import cv2
        import numpy as np
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from extractor360.ui.main_window import MainWindow
        from extractor360.core.processor import ProcessingWorker
        app=QApplication([])
        def until(predicate):
            deadline=time.monotonic()+15
            while not predicate():
                app.processEvents()
                time.sleep(.005)
                assert time.monotonic()<deadline, 'Qt lifecycle timeout'
            app.processEvents()
        media=Path('pano.png').resolve()
        cv2.imwrite(str(media),np.zeros((32,64,3),np.uint8))
        window=MainWindow()
        window.default_settings.update(resolution=32, layout_mode='cube', interval_unit='Frames', interval_value=1)
        window.show()
        video=Path('video.avi').resolve()
        encoder=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,32))
        assert encoder.isOpened()
        for value in (20,60,100): encoder.write(np.full((32,64,3),value,np.uint8))
        encoder.release()
        window.add_videos_from_paths([str(media),str(video)])
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: not window.is_processing)
        assert window.jobs[0].status=='Done'
        first=Path(window.jobs[0].result['output_dir'])
        assert len(list(first.glob('*.jpg')))==6
        assert window.jobs[1].status=='Done'
        assert len(list(Path(window.jobs[1].result['output_dir']).glob('*.jpg')))==18
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: not window.is_processing)
        assert window.jobs[0].status=='Done'
        assert Path(window.jobs[0].result['output_dir'])!=first
        window.jobs[0].settings['resolution']=-1
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: not window.is_processing)
        assert window.jobs[0].status=='Error'
        window.jobs[0].settings['resolution']=32
        original=ProcessingWorker._process_video
        def slow(self, *args):
            while self.is_running:
                time.sleep(.005)
        ProcessingWorker._process_video=slow
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: window.jobs[0].status=='Processing')
        window.close()
        until(lambda: not window.isVisible())
        assert window.jobs[0].status=='Cancelled'
        ProcessingWorker._process_video=original
        print('LIFECYCLE_OK')
    ''')
    env=dict(os.environ, QT_QPA_PLATFORM='offscreen', EXTRACTOR360_CONFIG_DIR=str(tmp_path/'config'), PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result=subprocess.run([sys.executable,'-c',script],cwd=tmp_path,env=env,text=True,capture_output=True,timeout=45)
    assert result.returncode==0, result.stdout+result.stderr
    assert 'LIFECYCLE_OK' in result.stdout
    assert 'Traceback' not in result.stderr
    assert 'QThread: Destroyed' not in result.stderr
