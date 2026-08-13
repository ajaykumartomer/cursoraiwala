import unittest

from akt_video_processor import FILTER_COMPLEX, build_ffmpeg_cmd


class FfmpegSafePathTests(unittest.TestCase):
    def test_command_uses_only_temp_names(self):
        nasty = "My Suggestions To @bjp4india   #ugcguidelines #narendramodi.mp4"
        cmd = build_ffmpeg_cmd("ffmpeg", "input.mp4", "bg.mp4", "output.mp4")
        joined = " ".join(cmd)
        self.assertNotIn("@", joined)
        self.assertNotIn("#ugc", joined)
        self.assertNotIn(nasty, joined)
        self.assertEqual(cmd[cmd.index("-i") + 1], "input.mp4")
        self.assertIn("-filter_complex", cmd)
        self.assertIn("[vout]", cmd)
        self.assertIn(FILTER_COMPLEX, cmd)

    def test_no_shell_metacharacters_from_windows_path(self):
        cmd = build_ffmpeg_cmd(
            "ffmpeg",
            "input.mp4",
            "bg.mp4",
            "output.mp4",
        )
        self.assertTrue(all(not arg.startswith("C:\\") for arg in cmd[1:]))
        self.assertNotIn("amovie=", FILTER_COMPLEX)


if __name__ == "__main__":
    unittest.main()
