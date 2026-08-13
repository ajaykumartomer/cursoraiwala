import unittest
from pathlib import Path

from akt_video_processor import build_ffmpeg_cmd, filter_file, script_dir


class FfmpegSafePathTests(unittest.TestCase):
    def test_command_uses_temp_names_and_filter_script(self):
        nasty = "My Suggestions To @bjp4india   #ugcguidelines #narendramodi.mp4"
        script = str(filter_file(True))
        cmd = build_ffmpeg_cmd(
            "ffmpeg",
            "input.mp4",
            "output.mp4",
            audio_name="bg.mp4",
            filter_script=script,
        )
        joined = " ".join(cmd)
        self.assertNotIn("@bjp", joined)
        self.assertNotIn("#ugc", joined)
        self.assertNotIn(nasty, joined)
        self.assertEqual(cmd[cmd.index("-i") + 1], "input.mp4")
        self.assertIn("-ss", cmd)
        self.assertEqual(cmd[cmd.index("-ss") + 1], "4")
        self.assertIn("-filter_complex_script", cmd)
        self.assertNotIn("-filter_complex", cmd)
        self.assertIn("-stream_loop", cmd)

    def test_filter_file_has_no_amovie_windows_path(self):
        text = filter_file(True).read_text(encoding="utf-8")
        self.assertNotIn("amovie=", text)
        self.assertIn("[2:a]", text)
        self.assertIn("overlay=1:enable=", text)
        self.assertTrue((script_dir() / "akt_filter_bg2.txt").is_file())

    def test_no_audio_command_omits_loop_input(self):
        cmd = build_ffmpeg_cmd(
            "ffmpeg",
            "input.mp4",
            "output.mp4",
            audio_name=None,
            filter_script=str(filter_file(False)),
        )
        self.assertNotIn("-stream_loop", cmd)
        self.assertEqual(cmd.count("-i"), 2)


if __name__ == "__main__":
    unittest.main()
