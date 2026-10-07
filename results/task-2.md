# Task 2: імпульси для Японії та Півд.-Сх. Азії на Full

Без нового коду: лише варіанти параметрів `agents/mpc_chip` (`pulse_weeks`, `pulse_grids`).
Раннер: `outputs/variants.py full 0 devpick:2,2,1,1 ... 4` (6 dev-епізодів Full, entropy 0, 4 воркери, 4 ядра).

## Раунд 1: завдання як є (`outputs/task2_variants.json`)

```
full, entropy 0, 6 episodes; diff = variant - mpc_chip, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
mpc_chip                  0.5802  0.517  0.692  0.568  0.522  +0.0000  [+0.0000, +0.0000]     nan%      0
pulse_twkrjpsea_15        0.6798  0.675  0.723  0.617  0.712  +0.0996  [+0.0573, +0.1475]   100.0%      0  <-- better
pulse_jpsea_15            0.5972  0.553  0.700  0.561  0.522  +0.0170  [+0.0148, +0.0194]   100.0%      0  <-- better
pulse_jpsea_25            0.5794  0.535  0.682  0.544  0.496  -0.0007  [-0.0041, +0.0029]    31.1%      0
```
results: `outputs/variants/task2_variants_full_0_1007-1428/results.json`

## Раунд 2 (додатково): чи дає JP+SEA щось понад TW+KR? (`outputs/task2_vs_twkr.json`)

Ті самі 6 епізодів, базою тут є `pulse_twkr_15`.

```
full, entropy 0, 6 episodes; diff = variant - pulse_twkr_15, 90% paired interval
variant                      RSS     L1     L2     L3     L4     diff  interval               better%  fallb
pulse_twkr_15             0.6596  0.636  0.713  0.621  0.704  +0.0000  [+0.0000, +0.0000]     nan%      0
pulse_twkrjpsea_15        0.6798  0.675  0.723  0.617  0.712  +0.0202  [+0.0120, +0.0293]   100.0%      0  <-- better
pulse_twkrjpsea_25        0.6468  0.635  0.697  0.594  0.658  -0.0128  [-0.0203, -0.0043]     0.0%      0  <-- worse
```
results: `outputs/variants/task2_vs_twkr_full_0_1007-1455/results.json`

## Висновок

- Найкраще: `pulse_weeks 1.5` на `grid_tw, grid_kr, grid_jp, grid_sea`. Це **+0.0996** до `mpc_chip` на Full-6.
  Приблизно +0.08 з цього дають TW+KR, а JP+SEA додають ще **+0.020** (інтервал [+0.012, +0.029]).
  Найбільший приріст на L1 (+0.16), а саме L1 має вагу 50%.
- 2.5 тижня гірше, ніж 1.5, в обох наборах мереж, тож довший імпульс не допомагає.
- Лише JP+SEA без TW+KR дає мало (+0.017).
- Обмеження: тільки 6 dev-епізодів, на Small не перевіряли, свіжий root теж не перевіряли (див. task 7).
  `sbf check` не запускали, бо змінюються лише параметри. 0 fallback-тижнів у всіх прогонах.
- Несподіванка: хоч кеш із `cache/sbf-cache.tgz` розпаковано, референси для devpick:2,2,1,1 будувалися 1423 с.
  Отже, кеш покриває ці епізоди не повністю (або ключ кешу не збігся). Повторний прогін уже брав їх із кешу (1 с).
