# 医美演示库 `ma_*` 表一览（表名 → 一句话业务说明）

来源：`db/med_aesthetic_sales_models.py` 中类文档字符串，共 **55** 张表。问数接口默认仅允许访问 `ma_` 前缀表。

| 表名 | 一句话说明 |
|------|------------|
| `ma_organization` | 法人/集团主体：可下辖多家分院，承载证照与对外签约主体信息。 |
| `ma_branch` | 分院/门店：一线接诊与收银发生地，线索与订单多按分院隔离。 |
| `ma_department` | 部门：销售、咨询、护理等，支持树形 parent 自关联。 |
| `ma_employee` | 员工主数据：咨询师、医生、前台等，与销售岗可一对多扩展。 |
| `ma_sales_team` | 销售团队：网咨、现场销售等编组，便于目标拆分与组长管理。 |
| `ma_salesperson` | 销售人员扩展：与员工一对一，挂团队、等级、企微与月度配额。 |
| `ma_customer` | 客户主档：成交与会员体系的中心实体，含归属销售与会员等级。 |
| `ma_customer_profile` | 客户画像：肤质、诉求、预算等，支撑咨询话术与推荐模型。 |
| `ma_lead_source` | 线索来源字典：信息流、老带新、地推等，用于 ROI 与渠道结算。 |
| `ma_lead` | 线索：未转客户前的潜客，含意向项目、评分与分配销售。 |
| `ma_lead_followup` | 线索跟进记录：电话、企微、到院等每次触达留痕。 |
| `ma_sales_pipeline_stage` | 销售漏斗阶段：各阶段名称、排序与赢单概率，可按分院配置。 |
| `ma_opportunity` | 销售商机：关联客户与可选线索，承载预计金额与关单日期。 |
| `ma_appointment` | 客户预约：项目、时段、咨询师与状态，连接网电与前台。 |
| `ma_visit_record` | 到院接待记录：是否初诊、接待人、现场备注。 |
| `ma_consultation` | 面诊咨询单：主诉、医生参与、诊断摘要，连接治疗方案。 |
| `ma_consultant_schedule` | 咨询师排班：按日时段与最大接诊数，控预约库存。 |
| `ma_product_category` | 品项分类：树形 parent，如「面部年轻化」下挂具体项目。 |
| `ma_product_sku` | 可售卖 SKU：单次治疗、药品支数等，含标价与成本参考。 |
| `ma_price_list_version` | 价目表版本：分院+生效区间，审批人留痕。 |
| `ma_price_list_item` | 价目表明细：每 SKU 在版本下的执行价与底价。 |
| `ma_package_bundle` | 打包套餐：多 SKU 组合价，sku_ids_json 存 ID 列表。 |
| `ma_competitor_price` | 竞品采价：市场调研，辅助定价与话术。 |
| `ma_treatment_plan` | 治疗方案：面诊后结构化方案，含整单折扣前金额。 |
| `ma_treatment_plan_line` | 治疗方案明细行：SKU、数量、单价与小计。 |
| `ma_quotation` | 报价单：对客户正式报价，含有效期与状态。 |
| `ma_order` | 销售订单：总金额、已付、状态，可关联商机。 |
| `ma_order_line` | 订单明细：SKU 或套餐行，含分摊折扣与行金额。 |
| `ma_contract` | 电子/纸质合同：模板、签署时间、PDF 存储地址。 |
| `ma_deposit_ledger` | 定金台账：每笔收退与客户、订单关联，便于对账。 |
| `ma_payment` | 收款流水：渠道、第三方单号、状态。 |
| `ma_refund` | 退款申请与结果：审批人、原因、状态。 |
| `ma_installment_plan` | 分期方案：与订单一对一，首付、月供、合作金融机构。 |
| `ma_installment_schedule` | 分期还款计划：每期应还日、实还时间、状态。 |
| `ma_member_card` | 会员卡：等级、储值余额、积分余额、开卡日。 |
| `ma_points_ledger` | 积分流水：每笔增减、业务类型、关联订单。 |
| `ma_coupon_template` | 优惠券模板：满减规则、面值类型、最低消费与有效天数。 |
| `ma_coupon_issue` | 发券实例：一券一码、使用状态、核销订单。 |
| `ma_gift_with_purchase` | 满赠记录：订单维度的赠品发放，便于库存与成本核算。 |
| `ma_commission_rule` | 提成规则：按分院+品项分类+比例+生效区间。 |
| `ma_commission_detail` | 销售提成明细：按订单/销售/SKU 拆账，归属结算月。 |
| `ma_doctor_commission_split` | 医生分润：按订单行拆给执行医生，比例+金额落库。 |
| `ma_sales_target` | 销售个人目标：按月营收与可选单量目标。 |
| `ma_daily_sales_stat` | 分院日统计：线索、预约、到院、订单数与营收汇总（预聚合）。 |
| `ma_channel_partner` | 渠道合作方：医美转诊、异业、KOL 等，含联系人及返利策略。 |
| `ma_channel_settlement` | 渠道月度结算：线索量、成交量、结算金额与状态。 |
| `ma_marketing_campaign` | 营销活动：时间窗、预算、UTM 来源标记。 |
| `ma_campaign_enrollment` | 活动报名：客户参与记录，用于到院礼与短信触达。 |
| `ma_referral_reward` | 老带新奖励：推荐人、被推荐人、关联订单与积分/现金奖励。 |
| `ma_aftercare_task` | 术后回访任务：类型、截止时间、执行人、完成状态。 |
| `ma_satisfaction_survey` | 满意度与 NPS：可关联到院记录，收集评论。 |
| `ma_complaint_ticket` | 投诉工单：分类、描述、责任人、处理状态。 |
| `ma_customer_tag` | 客户标签字典：编码、名称、分组（销售/医学等）。 |
| `ma_customer_tag_rel` | 客户与标签多对多：打标时间与客户、标签外键。 |
| `ma_inventory_batch` | 耗材/药品批次：分院库存、批号、效期、数量与单位成本。 |

## 同库非 `ma_*` 表（Agent 服务用）

见 `db/models.py`：`chat_history`、`task_record`、`agent_task_run`、`api_log`、`error_log` 等；**当前问数 SQL 白名单不包含这些表**。
