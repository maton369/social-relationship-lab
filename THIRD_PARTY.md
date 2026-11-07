# Third-party software

公開PyPIの固定バージョンのwheelを使用しています。正式版 `Social_Relationship_Lab_v3.toe` は、Mac Apple Silicon用とWindows x64用のigraph・leidenalg・texttableおよび各配布物のライセンスを内蔵し、初回起動時にローカル展開します。アプリ起動時のダウンロードやpip実行は行いません。NumPyはTouchDesigner内蔵版を使い、追加で同梱しません。開発用 `vendor/` のNumPyは単体テスト用です。

| Package | Version | License / included notice |
| --- | --- | --- |
| leidenalg | 0.10.2 | GPL-3.0-or-later; [LICENSE](vendor/leidenalg-0.10.2.dist-info/LICENSE) |
| igraph | 0.11.9 | GPL-2.0-or-later; [LICENSE](vendor/igraph-0.11.9.dist-info/licenses/LICENSE) |
| NumPy | 2.2.6 | BSD-3-Clause and bundled library notices; [LICENSE](vendor/numpy-2.2.6.dist-info/LICENSE.txt) |
| texttable | 1.7.0 | MIT; [LICENSE](vendor/texttable-1.7.0.dist-info/LICENSE) |

各packageの `.dist-info` に配布元のメタデータ・ライセンスを保持しています。上流コード：[leidenalg](https://github.com/vtraag/leidenalg/tree/0.10.2)、[python-igraph](https://github.com/igraph/python-igraph/tree/0.11.9)、[NumPy](https://github.com/numpy/numpy/tree/v2.2.6)、[texttable](https://github.com/foutaise/texttable)。ライセンス条件は各同梱文書に従います。今回作成したコードから、公開実装を外部ライブラリとして呼び出します。

再取得には対象環境のPythonを指定し、`uv pip install --python <Pythonのパス> --target <このフォルダ>/vendor --only-binary=:all: -r requirements.txt` を使用できます。既存のvendorとの混在を避け、別フォルダに用意してから切り替えてください。
