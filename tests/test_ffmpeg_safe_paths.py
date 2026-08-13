import unittest

from akt_video_processor import build_ffmpeg_cmd, filter_file


class FfmpegSafePathTests(unittest.TestCase):
    def test_command_matches_original_shape(self):
        script = str(filter_file(True))
        cmd = build_ffmpeg_cmd("ffmpeg", "input.mp4", "output.mp4", script)
        joined = " ".join(cmd)
        self.assertNotIn("@bjp", joined)
        self.assertEqual(cmd[cmd.index("-i") + 1], "input.mp4")
        self.assertEqual(cmd[cmd.index("-ss") + 1], "4")
        self.assertEqual(cmd.count("-i"), 2)
        self.assertIn("-filter_complex_script", cmd)
        self.assertNotIn("-stream_loop", cmd)

    def test_filter_uses_original_amovie_relative_path(self):
        text = filter_file(True).read_text(encoding="utf-8")
        self.assertIn("amovie=aud/bg2.mp4:loop=9999", text)
        self.assertNotIn("C:", text)
        self.assertIn("(in_h-out_h)/1.5 +((in_h-out_h)/1.5)*sin(t*0.2)", text)


if __name__ == "__main__":
    unittest.main()
