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
        print('LIFECYCLE_STAGE: QApplication')
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
        print('LIFECYCLE_STAGE: MainWindow')
        window=MainWindow()
        window.default_settings.update(resolution=32, layout_mode='cube', interval_unit='Frames', interval_value=1)
        window.show()
        video=Path('video.avi').resolve()
        encoder=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,32))
        assert encoder.isOpened()
        for value in (20,60,100): encoder.write(np.full((32,64,3),value,np.uint8))
        encoder.release()
        print('LIFECYCLE_STAGE: import media')
        window.add_videos_from_paths([str(media),str(video)])
        print('LIFECYCLE_STAGE: first extraction')
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: not window.is_processing)
        assert window.jobs[0].status=='Done'
        first=Path(window.jobs[0].result['output_dir'])
        assert len(list(first.glob('*.jpg')))==6
        assert window.jobs[1].status=='Done'
        assert len(list(Path(window.jobs[1].result['output_dir']).glob('*.jpg')))==18
        print('LIFECYCLE_STAGE: second extraction')
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: not window.is_processing)
        assert window.jobs[0].status=='Done'
        assert Path(window.jobs[0].result['output_dir'])!=first
        window.jobs[0].settings['resolution']=-1
        print('LIFECYCLE_STAGE: invalid settings')
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: not window.is_processing)
        assert window.jobs[0].status=='Error'
        window.jobs[0].settings['resolution']=32
        original=ProcessingWorker._process_video
        def slow(self, *args):
            while self.is_running:
                time.sleep(.005)
        ProcessingWorker._process_video=slow
        print('LIFECYCLE_STAGE: cancellation')
        QTest.mouseClick(window.extract_btn,Qt.LeftButton)
        until(lambda: window.jobs[0].status=='Processing')
        window.close()
        until(lambda: not window.isVisible())
        assert window.jobs[0].status=='Cancelled'
        ProcessingWorker._process_video=original
        print('LIFECYCLE_OK')
    ''')
    env=dict(os.environ, QT_QPA_PLATFORM='offscreen', EXTRACTOR360_CONFIG_DIR=str(tmp_path/'config'), PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result=subprocess.run([sys.executable,'-X','faulthandler','-u','-c',script],cwd=tmp_path,env=env,text=True,capture_output=True,timeout=45)
    assert result.returncode==0, result.stdout+result.stderr
    assert 'LIFECYCLE_OK' in result.stdout


def test_preview_and_removed_thumbnail_queued_delivery(tmp_path):
    script = textwrap.dedent('''
        import gc
        import threading
        from pathlib import Path
        import cv2
        import numpy as np
        from PySide6.QtCore import QCoreApplication, QEvent, QThread, QThreadPool
        from PySide6.QtWidgets import QApplication
        from extractor360.core.job import Job
        from extractor360.core.settings_manager import SettingsManager
        from extractor360.ui.preview_widget import PreviewWidget, PreviewDelivery
        from extractor360.ui.video_card import VideoCard

        app = QApplication([])
        media = Path('flat.png').resolve()
        assert cv2.imwrite(str(media), np.full((32,64,3),80,np.uint8))
        calls = []
        class Preview(PreviewWidget):
            def _display_image(self, image, generation):
                assert QThread.currentThread() == app.thread()
                calls.append(generation)
                super()._display_image(image, generation)
        preview = Preview()
        settings = dict(SettingsManager.DEFAULT_SETTINGS, is_360=False)
        preview.update_preview(str(media), settings)
        preview._debounce.stop()
        preview._run_pending()
        assert preview.threadpool.waitForDone(15000)
        gc.collect()  # the runnable is gone, its queued result must survive
        assert calls == []
        app.processEvents()
        assert calls == [preview._generation]
        assert preview.cached_image.size().width() == 64
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert preview.findChildren(PreviewDelivery) == []

        started, release = threading.Event(), threading.Event()
        original = cv2.imread
        def delayed(*args, **kwargs):
            started.set()
            assert release.wait(10)
            return original(*args, **kwargs)
        cv2.imread = delayed
        card = VideoCard(Job(file_path=str(media), settings=settings))
        assert started.wait(10)
        card._cleanup_thread()
        card.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        release.set()
        assert QThreadPool.globalInstance().waitForDone(15000)
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        cv2.imread = original
        preview.shutdown()
        preview.close()
        print('QUEUED_DELIVERY_OK')
    ''')
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', EXTRACTOR360_CONFIG_DIR=str(tmp_path/'config'), PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    result = subprocess.run([sys.executable, '-X', 'faulthandler', '-u', '-c', script], cwd=tmp_path, env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'QUEUED_DELIVERY_OK' in result.stdout
    assert 'Traceback' not in result.stderr
    assert 'Traceback' not in result.stderr
    assert 'QThread: Destroyed' not in result.stderr
