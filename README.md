# schemadrift

`schemadrift` 只使用 Python 标准库，对两份 CSV 的表头、列类型、列位置和主键重复情况进行差异分析，并生成确定性的 JSON 报告。

## 运行方式

```bash
python -m schemadrift.cli --old demo/v1.csv --new demo/v2.csv --threshold 0.6 --out out/report.json
```

参数：

- `--old`：旧版 CSV，必需。
- `--new`：新版 CSV，必需。
- `--primary-key`：主键列名，默认 `order_id`。
- `--threshold`：重命名相似度阈值，默认 `0.6`。
- `--out`：JSON 报告输出路径，必需。

命令结束后会在 stdout 打印一行摘要，包含变更数、五类变更分布、重命名数和重复主键数。

## 列名归一

列名按以下顺序归一：

1. 去掉首尾空白。
2. 转小写。
3. 连续空白和连字符统一成下划线。
4. 连续下划线压缩成一个下划线。

因此 `customer name`、`customer_name` 和 `Customer-Name` 都会归一成 `customer_name`。归一后同名的列优先配成同一列，并保留报告中的原始列名。

## 取值归一与空值

类型推断前，每个单元格先去掉首尾空白。空值按去空白后的小写形式判断，词表正好包含：

- 空串 `""`
- `null`
- `none`
- `na`
- `n/a`
- `-`

空值不参与类型推断。整列没有非空值时，类型为 `null`。

## 数值识别

数值解析会依次执行：

1. 去掉货币符号：`$`、`€`、`£`、`¥`、`￥`。
2. 不区分大小写地去掉货币代码：`USD`、`EUR`、`GBP`、`CNY`、`RMB`。
3. 去掉千分位逗号。
4. 整体被圆括号包住，或末尾带减号时，识别为负数。
5. 剩余内容必须只由数字和最多一个小数点组成。

小数点写法参与类型判断：`100.00` 是 `float`，`100` 是 `integer`。无法按上述规则读取的值不是数值。

## 类型推断

- 主键列无论取值是什么，类型一律为 `text`，因此 `000123` 不会被推断成整数。
- 非主键列只看非空值。
- 没有非空值：`null`。
- 全部匹配 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM:SS`：`date`。
- 全部能按数值读取：任一值带小数点为 `float`，否则为 `integer`。
- 其他情况：`string`。

## 编辑距离与相似度

编辑距离把插入、删除、替换的代价都记为 1，取把一个归一化列名变成另一个的最小代价。

相似度公式：

```text
similarity = 1 - edit_distance / max(len(old_name), len(new_name))
```

结果按四舍五入保留 4 位小数。例如：

- `created_at` 与 `created_ts`：编辑距离 2，最大长度 10，相似度 `0.8`。
- `gross_amount` 与 `gross_amount_cny`：编辑距离 4，最大长度 16，相似度 `0.75`。

## 重命名条件

先配对归一后同名的列，只有两版中配不上的列才进入重命名候选。某个候选必须同时满足：

1. 两列在各自表头中的位置相同。
2. 推断类型一致。
3. 归一化名字的相似度达到阈值。

候选按相似度从高到低匹配；每个列最多参与一次重命名。未匹配上的旧列判为 `removed`，未匹配上的新列判为 `added`。

## 重排判断

重排只检查两版都存在的列，新增列和删除列不参与。

把共有列按 v1 顺序排列，再查看它们在 v2 中的位置。只有 v1 顺序中相邻的两列在 v2 中出现逆序，才记录为一个逆序列对。因此在中间插入 `tax_rate` 或删除 `legacy_code`，不会把后续列整体判成重排。

报告中的 `reordered` 只有一条变更，其 `evidence.columns` 按 v1 顺序列出所有逆序列对；每个列对中，v1 顺序在前的列名排在前面。

## 报告结构

顶层固定包含五个字段：

- `v1_columns`：旧版列信息。
- `v2_columns`：新版列信息。
- `changes`：结构和类型变更。
- `duplicate_primary_keys`：按 `v1`、`v2` 分组的重复主键值。
- `summary`：统计摘要。

每个列对象正好包含：

- `name`：原始列名。
- `type`：推断类型。
- `position`：从 0 开始的列位置。

每条变更正好包含 `change`、`field`、`evidence`：

- `added`：`evidence` 含 `position`、`type`。
- `removed`：`evidence` 含 `position`、`type`。
- `renamed`：`evidence` 含 `old_name`、`new_name`、`similarity`。
- `type_changed`：`evidence` 含 `old_type`、`new_type`。
- `reordered`：`evidence` 含 `columns`。

`summary` 正好包含 `added`、`removed`、`renamed`、`type_changed`、`reordered`、`duplicate_primary_keys`、`threshold` 七个字段。报告使用固定键顺序、固定换行和 UTF-8 编码，同一份输入重复运行会逐字节一致。

## 测试

```bash
python -m unittest test_schemadrift -v
```
