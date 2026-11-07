# 実装した機構と先行研究

以下は実装の着想と、独自の仮定を分けた記録。論文が今回の係数、好感度尺度、収束、分裂を保証したとは扱わない。
既存のCPM・Leiden等についてはREADMEおよびTHIRD_PARTY.mdも参照。

| 文献 | 参照した内容 | 実装 | 一致度・確認範囲 |
| --- | --- | --- | --- |
| Alistair Sutcliffe, Di Wang, Robin Dunbar (2012), *Social Relationships and the Emergence of Social Networks*, JASSS 15(4), 3. https://doi.org/10.18564/jasss.2059 | §2.2–2.6：交流履歴、信頼の蓄積・減衰、強い信頼の緩和、限られた交流時間、相手選択 | `social_dynamics.py` の初期信頼・protection/learn/background、`model.py` の信頼履歴 | B：考え方を参考に独自拡張。原論文の信頼更新・進化モデルは再現していない。全文HTML確認：https://www.jasss.org/15/4/3.html |
| David G. Rand, Samuel Arbesman, Nicholas A. Christakis (2011), *Dynamic social networks promote cooperation in experiments with humans*, PNAS 108(48), 19193–19198. https://doi.org/10.1073/pnas.1108243108 | 過去の協力行動に応じた関係形成・切断（link reciprocity）と協力の関係 | `social_dynamics.py` の相手選択・受諾、自律交流後の `model.py` の関係更新 | B：実験の発想を参照。囚人のジレンマの利得表や被験者の意思決定を再現していない。原研究は関係数の上限を課しておらず、今回の時間予算は同論文由来ではない。著者所属機関公開PDF本文確認。 |
| Terence D. Dores Cruz et al. (2021), *Gossip and reputation in everyday life*, Philosophical Transactions of the Royal Society B 376, 20200301. https://doi.org/10.1098/rstb.2020.0301 | 噂による評判更新・将来の相手選択との関連、送り手と対象の利害関係による真偽判断 | `social_dynamics.py:credibility`、`model.py`の噂の受信・評価ログ、`runtime.py`の噂パネル | B：概念を参照。Tを掛ける式・対立割引係数0.35はCの独自仮定。質問紙上の評価とシミュレーションのX/Tは同じ尺度ではない。大学リポジトリの全文PDF確認。 |

Randらの公開PDF：https://humannaturelab.net/sites/default/files/pdf/paper/126-Dynamic-Social-Networks-Promote-Cooperation-in-Experiments-with-Humans.pdf

Dores Cruzらの公開PDF：https://research-repository.st-andrews.ac.uk/bitstream/10023/32167/1/Dores-Cruz_2021_PTB_Gossip-reputation_CC.pdf

## 論文由来ではない部分（区分C）

- 初期信頼U(0.2,0.8)、初期信頼と好感度・関係の条件付き生成。
- 攻撃の緩和係数0.85、信頼学習率0.18、経時減衰0.003。
- 行動を予約して一時刻の予算を人数で分ける方式、受諾時の双方1単位、拒絶時の誘い手0.25単位。
- 相手選択スコア2X+1.5T+0.5A、探索率0.18、受諾確率sigmoid(2X+T)。
- 自主的な交流を肯定的な経験として加算する式、断られた場合の評価低下、維持不足による好感度減衰。
- 噂の信用をTとXから計算する式。真偽や送り手の意図をモデル内で判定したものではない。
- 3シード・80時刻という今回の検証規模。必要サンプル数を算定した統計設計ではない。

式・実際の値と更新順序：[social-dynamics.md](social-dynamics.md)。実験の全条件と出力：[結果記録](experiments/social_dynamics/results.md)。
