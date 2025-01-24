import test


class TestMatchArtifactByOcrFull(test.ZzzTestBase):

    def __init__(self, *args, **kwargs):
        test.ZzzTestBase.__init__(self, *args, **kwargs)

    def test_match_artifact_by_ocr_full(self):
        self.ctx.lost_void.load_artifact_data()

        ans = self.ctx.lost_void.match_artifact_by_ocr_full('[终结]蓄势架子鼓')

        t1 = self.ctx.lost_void.match_artifact_by_ocr_full('终吉 势架子鼓')
        self.assertEqual(ans, t1, ans.display_name)