# -*- coding: utf-8 -*-
"""
医美机构销售域演示表（约 55 张），贴近 CRM、收银、渠道、提成等真实业务。
仅用于演示与 Agent 样例查询；未覆盖生产级权限、审计、软删除、乐观锁等。
"""

# date：仅日期（生日、生效日等）；datetime：含时分秒的时间戳
from datetime import date, datetime

# SQLAlchemy 列类型与表级约束
from sqlalchemy import Boolean  # 布尔；SQLite 中常以 0/1 存储
from sqlalchemy import Column  # ORM 字段声明
from sqlalchemy import Date  # 日历日期，不含时区
from sqlalchemy import DateTime  # 日期时间，默认用本地 naive 时间
from sqlalchemy import ForeignKey  # 外键，仅文档与部分数据库强制；SQLite 需 PRAGMA 才校验
from sqlalchemy import Integer  # 32 位整型，主键与计数常用
from sqlalchemy import Numeric  # 定点小数，金额与比例用，避免浮点误差
from sqlalchemy import String  # 定长上限的变长字符串
from sqlalchemy import Text  # 大文本，如 JSON 串、长描述

# 与项目共用的 declarative Base，所有表注册到同一 metadata
from .base import Base


# ---------------------------------------------------------------------------
# 组织与人员：集团、分院、部门、员工、销售编制
# ---------------------------------------------------------------------------


class MaOrganization(Base):
    """法人/集团主体：可下辖多家分院，承载证照与对外签约主体信息。"""

    __tablename__ = "ma_organization"  # 数据库实际表名，前缀 ma_ 表示 med aesthetic 演示域
    id = Column(Integer, primary_key=True)  # 主键，自增整型
    name = Column(String(128), nullable=False)  # 机构常用名或品牌名，必填
    legal_name = Column(String(256))  # 营业执照上的法定名称，可为空
    license_no = Column(String(64))  # 医疗机构执业许可证号等业务证照编号
    city = Column(String(64))  # 机构主要所在城市，用于报表与地域维度
    status = Column(String(20), default="active")  # 生命周期：active 营业中 / 其他自定义
    created_at = Column(DateTime, default=datetime.now)  # 记录写入时间，新建时自动填充


class MaBranch(Base):
    """分院/门店：一线接诊与收银发生地，线索与订单多按分院隔离。"""

    __tablename__ = "ma_branch"  # 分院主数据表
    id = Column(Integer, primary_key=True)  # 主键
    org_id = Column(Integer, ForeignKey("ma_organization.id"), index=True)  # 归属集团，建索引便于按集团筛
    branch_code = Column(String(32), unique=True)  # 院内唯一编码，对接 HIS/财务时常用
    name = Column(String(128))  # 分院展示名称，如「徐汇旗舰院」
    address = Column(String(256))  # 详细地址，到院导航与合同展示
    phone = Column(String(32))  # 分院总机或前台电话
    opened_at = Column(Date)  # 开业日期，用于店龄与周年活动
    status = Column(String(20), default="open")  # open 营业 / 筹备 / 停业等
    created_at = Column(DateTime, default=datetime.now)  # 数据落库时间


class MaDepartment(Base):
    """部门：销售、咨询、护理等，支持树形 parent 自关联。"""

    __tablename__ = "ma_department"  # 部门表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 部门所属分院
    name = Column(String(64))  # 部门名称，如「网电销售一组」
    dept_type = Column(String(32))  # 部门类型枚举：sales / consult / medical 等，便于权限与报表
    parent_id = Column(Integer, ForeignKey("ma_department.id"), nullable=True)  # 上级部门，空表示根
    created_at = Column(DateTime, default=datetime.now)  # 创建时间


class MaEmployee(Base):
    """员工主数据：咨询师、医生、前台等，与销售岗可一对多扩展。"""

    __tablename__ = "ma_employee"  # 员工表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 人事归属分院，借调场景可再扩展
    emp_no = Column(String(32), unique=True)  # 工号，全院或集团内唯一
    name = Column(String(64))  # 真实姓名或对内花名策略由业务定
    mobile = Column(String(20))  # 工作手机，登录与通知
    job_title = Column(String(64))  # 岗位名称，如「资深医美咨询师」
    hire_date = Column(Date)  # 入职日期，工龄与年假计算
    status = Column(String(20), default="active")  # active 在职 / 离职等
    created_at = Column(DateTime, default=datetime.now)  # 建档时间


class MaSalesTeam(Base):
    """销售团队：网咨、现场销售等编组，便于目标拆分与组长管理。"""

    __tablename__ = "ma_sales_team"  # 销售团队表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 团队所属分院
    team_name = Column(String(64))  # 团队对外或对内名称
    leader_emp_id = Column(Integer, ForeignKey("ma_employee.id"), nullable=True)  # 组长员工，可为空（未指定）
    created_at = Column(DateTime, default=datetime.now)  # 团队创建时间


class MaSalesperson(Base):
    """销售人员扩展：与员工一对一，挂团队、等级、企微与月度配额。"""

    __tablename__ = "ma_salesperson"  # 销售岗扩展表
    id = Column(Integer, primary_key=True)  # 主键
    employee_id = Column(Integer, ForeignKey("ma_employee.id"), unique=True)  # 对应员工，一人最多一条销售扩展
    team_id = Column(Integer, ForeignKey("ma_sales_team.id"), nullable=True)  # 所属团队，独立顾问可为空
    level_code = Column(String(32))  # 职级编码，与提成阶梯表可关联
    wecom_id = Column(String(64))  # 企业微信 userid，用于加好友与跟进记录回写
    monthly_quota = Column(Numeric(12, 2), default=0)  # 当月业绩指标金额，元
    created_at = Column(DateTime, default=datetime.now)  # 开通销售账号时间


# ---------------------------------------------------------------------------
# 客户与线索：客户、画像、来源、线索、跟进、漏斗、商机
# ---------------------------------------------------------------------------


class MaCustomer(Base):
    """客户主档：成交与会员体系的中心实体，含归属销售与会员等级。"""

    __tablename__ = "ma_customer"  # 客户表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 主服务分院或建档分院
    customer_no = Column(String(32), unique=True)  # 客户编号，对外单据展示
    name = Column(String(64))  # 称呼或脱敏名
    gender = Column(String(8))  # 性别：男/女/未知等
    birthday = Column(Date, nullable=True)  # 生日，用于营销与年龄分层，可空
    mobile = Column(String(20), index=True)  # 手机号，高查询维度，建索引
    city = Column(String(64))  # 居住或工作城市
    first_source = Column(String(64))  # 首次获客渠道描述，可与线索来源字典对照
    owner_sales_id = Column(Integer, ForeignKey("ma_salesperson.id"), nullable=True)  # 当前归属销售，公海可为空
    member_level = Column(String(32), default="normal")  # 会员等级：normal / silver / gold 等
    created_at = Column(DateTime, default=datetime.now)  # 建档时间


class MaCustomerProfile(Base):
    """客户画像：肤质、诉求、预算等，支撑咨询话术与推荐模型。"""

    __tablename__ = "ma_customer_profile"  # 客户画像扩展表
    id = Column(Integer, primary_key=True)  # 主键
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), unique=True)  # 一对一挂客户
    skin_type = Column(String(32))  # 肤质分类：油性/干性/混合等
    concern_tags_json = Column(Text)  # JSON 数组字符串，存关注点标签，如法令纹、毛孔
    aesthetic_goal = Column(Text)  # 变美目标长文本，面诊记录摘要可同步
    budget_range = Column(String(32))  # 预算区间展示文案，如「2-4万」
    competitor_brands = Column(String(256))  # 曾对比过的竞品机构或品牌，逗号分隔等
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)  # 每次 UPDATE 自动刷新


class MaLeadSource(Base):
    """线索来源字典：信息流、老带新、地推等，用于 ROI 与渠道结算。"""

    __tablename__ = "ma_lead_source"  # 线索来源维表
    id = Column(Integer, primary_key=True)  # 主键
    code = Column(String(32), unique=True)  # 来源编码，程序与报表用
    name = Column(String(64))  # 来源中文名称，界面展示
    channel_type = Column(String(32))  # 大类：paid_social / referral / ooh 等
    cost_per_lead = Column(Numeric(10, 2), nullable=True)  # 预估单条线索成本，元，可空
    is_active = Column(Boolean, default=True)  # 是否仍在前端可选


class MaLead(Base):
    """线索：未转客户前的潜客，含意向项目、评分与分配销售。"""

    __tablename__ = "ma_lead"  # 线索表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 线索归属分院
    lead_no = Column(String(32), unique=True)  # 线索单号
    name = Column(String(64))  # 线索姓名
    mobile = Column(String(20), index=True)  # 手机，查重与跟进主键之一
    source_id = Column(Integer, ForeignKey("ma_lead_source.id"))  # 来源字典外键
    intent_project = Column(String(128))  # 意向项目简述，如「超声炮+水光」
    status = Column(String(32), default="new")  # new / contacted / converted / lost 等
    score = Column(Integer, default=0)  # 线索评分，规则引擎或人工打分
    assign_sales_id = Column(Integer, ForeignKey("ma_salesperson.id"), nullable=True)  # 分配销售，池子中可空
    created_at = Column(DateTime, default=datetime.now)  # 入库时间


class MaLeadFollowup(Base):
    """线索跟进记录：电话、企微、到院等每次触达留痕。"""

    __tablename__ = "ma_lead_followup"  # 线索跟进明细表
    id = Column(Integer, primary_key=True)  # 主键
    lead_id = Column(Integer, ForeignKey("ma_lead.id"), index=True)  # 所属线索
    sales_id = Column(Integer, ForeignKey("ma_salesperson.id"))  # 执行跟进的销售
    follow_type = Column(String(32))  # 跟进方式：call / wechat / visit 等
    content = Column(Text)  # 跟进内容全文
    next_action_at = Column(DateTime, nullable=True)  # 下次计划动作时间，可空
    created_at = Column(DateTime, default=datetime.now)  # 本条记录创建时间


class MaSalesPipelineStage(Base):
    """销售漏斗阶段：各阶段名称、排序与赢单概率，可按分院配置。"""

    __tablename__ = "ma_sales_pipeline_stage"  # 漏斗阶段表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 分院级漏斗定义
    stage_code = Column(String(32))  # 阶段编码，程序分支用
    stage_name = Column(String(64))  # 阶段中文名，如「方案洽谈」
    sort_order = Column(Integer, default=0)  # 看板从左到右排序，数值越小越靠前
    probability_pct = Column(Integer, default=0)  # 进入该阶段时期望赢单概率 0–100


class MaOpportunity(Base):
    """销售商机：关联客户与可选线索，承载预计金额与关单日期。"""

    __tablename__ = "ma_opportunity"  # 商机表
    id = Column(Integer, primary_key=True)  # 主键
    opp_no = Column(String(32), unique=True)  # 商机编号
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 关联客户
    lead_id = Column(Integer, ForeignKey("ma_lead.id"), nullable=True)  # 来源线索，直客建档可空
    stage_id = Column(Integer, ForeignKey("ma_sales_pipeline_stage.id"))  # 当前漏斗阶段
    owner_sales_id = Column(Integer, ForeignKey("ma_salesperson.id"))  # 商机负责人
    expected_amount = Column(Numeric(12, 2))  # 预计成交金额，元
    expected_close_date = Column(Date)  # 预计签约或关单日期
    lost_reason = Column(String(128), nullable=True)  # 输单原因，赢单或进行中可空
    status = Column(String(20), default="open")  # open / won / lost 等
    created_at = Column(DateTime, default=datetime.now)  # 商机创建时间


# ---------------------------------------------------------------------------
# 预约与到院：预约、接待、面诊、咨询师排班
# ---------------------------------------------------------------------------


class MaAppointment(Base):
    """客户预约：项目、时段、咨询师与状态，连接网电与前台。"""

    __tablename__ = "ma_appointment"  # 预约表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 预约分院
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 预约客户
    project_name = Column(String(128))  # 预约项目或事由简述
    appt_time = Column(DateTime)  # 预约到店时间
    consultant_emp_id = Column(Integer, ForeignKey("ma_employee.id"), nullable=True)  # 指定咨询师，可空
    source = Column(String(64))  # 预约入口：电话/小程序/三方等
    status = Column(String(32), default="booked")  # booked / completed / noshow / cancelled 等
    created_at = Column(DateTime, default=datetime.now)  # 预约下单时间


class MaVisitRecord(Base):
    """到院接待记录：是否初诊、接待人、现场备注。"""

    __tablename__ = "ma_visit_record"  # 到院记录表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 到院分院
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    visit_at = Column(DateTime)  # 实际到院签到时间
    reception_emp_id = Column(Integer, ForeignKey("ma_employee.id"))  # 接待人员工
    first_visit = Column(Boolean, default=True)  # 是否初诊到院
    notes = Column(Text)  # 接待现场备注，如皮肤检测摘要


class MaConsultation(Base):
    """面诊咨询单：主诉、医生参与、诊断摘要，连接治疗方案。"""

    __tablename__ = "ma_consultation"  # 面诊/咨询单表
    id = Column(Integer, primary_key=True)  # 主键
    consult_no = Column(String(32), unique=True)  # 咨询单号
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    consultant_emp_id = Column(Integer, ForeignKey("ma_employee.id"))  # 主诊咨询师
    doctor_emp_id = Column(Integer, ForeignKey("ma_employee.id"), nullable=True)  # 会诊医生，可空
    chief_complaint = Column(Text)  # 主诉
    diagnosis_summary = Column(Text)  # 诊断与建议摘要
    consult_at = Column(DateTime, default=datetime.now)  # 面诊发生时间


class MaConsultantSchedule(Base):
    """咨询师排班：按日时段与最大接诊数，控预约库存。"""

    __tablename__ = "ma_consultant_schedule"  # 咨询师排班表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 排班分院
    emp_id = Column(Integer, ForeignKey("ma_employee.id"), index=True)  # 排班员工（咨询师）
    work_date = Column(Date, index=True)  # 排班日期
    slot_start = Column(String(8))  # 时段开始，如「09:00」字符串便于展示
    slot_end = Column(String(8))  # 时段结束，如「18:00」
    max_appts = Column(Integer, default=8)  # 该日该咨询师最大可约人数


# ---------------------------------------------------------------------------
# 品项与价目：分类、SKU、价目版本、套餐、竞品采价
# ---------------------------------------------------------------------------


class MaProductCategory(Base):
    """品项分类：树形 parent，如「面部年轻化」下挂具体项目。"""

    __tablename__ = "ma_product_category"  # 品项分类表
    id = Column(Integer, primary_key=True)  # 主键
    parent_id = Column(Integer, ForeignKey("ma_product_category.id"), nullable=True)  # 父分类，空为一级
    name = Column(String(64))  # 分类名称
    sort_order = Column(Integer, default=0)  # 同级排序


class MaProductSku(Base):
    """可售卖 SKU：单次治疗、药品支数等，含标价与成本参考。"""

    __tablename__ = "ma_product_sku"  # 品项 SKU 表
    id = Column(Integer, primary_key=True)  # 主键
    sku_code = Column(String(48), unique=True)  # SKU 编码，对接库存与订单行
    name = Column(String(128))  # 对外展示名称
    category_id = Column(Integer, ForeignKey("ma_product_category.id"))  # 所属分类
    unit = Column(String(16), default="次")  # 计量单位：次/支/部位等
    list_price = Column(Numeric(12, 2))  # 划线价或标准零售价，元
    cost_price = Column(Numeric(12, 2), nullable=True)  # 内部成本参考，可空
    duration_minutes = Column(Integer, nullable=True)  # 标准操作时长分钟，排班用
    device_brand = Column(String(64), nullable=True)  # 设备或耗材品牌，如半岛超声炮
    is_combo = Column(Boolean, default=False)  # 是否组合/打包虚拟 SKU
    status = Column(String(20), default="on_sale")  # on_sale 上架 / 下架等


class MaPriceListVersion(Base):
    """价目表版本：分院+生效区间，审批人留痕。"""

    __tablename__ = "ma_price_list_version"  # 价目表头（版本）
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 适用分院
    version_code = Column(String(32))  # 版本号，如 PL-2026Q2
    effective_from = Column(Date)  # 生效起日（含）
    effective_to = Column(Date, nullable=True)  # 生效止日，空表示当前仍有效
    approved_by_emp_id = Column(Integer, ForeignKey("ma_employee.id"), nullable=True)  # 审批人
    created_at = Column(DateTime, default=datetime.now)  # 版本创建时间


class MaPriceListItem(Base):
    """价目表明细：每 SKU 在版本下的执行价与底价。"""

    __tablename__ = "ma_price_list_item"  # 价目表明细
    id = Column(Integer, primary_key=True)  # 主键
    price_list_id = Column(Integer, ForeignKey("ma_price_list_version.id"), index=True)  # 所属价目版本
    sku_id = Column(Integer, ForeignKey("ma_product_sku.id"), index=True)  # 品项 SKU
    sale_price = Column(Numeric(12, 2))  # 标准成交价/展示价
    min_price = Column(Numeric(12, 2), nullable=True)  # 咨询师可放行的底价，可空


class MaPackageBundle(Base):
    """打包套餐：多 SKU 组合价，sku_ids_json 存 ID 列表。"""

    __tablename__ = "ma_package_bundle"  # 套餐包表
    id = Column(Integer, primary_key=True)  # 主键
    bundle_code = Column(String(48), unique=True)  # 套餐编码
    name = Column(String(128))  # 套餐名称
    bundle_price = Column(Numeric(12, 2))  # 套餐整体售价
    sku_ids_json = Column(Text)  # JSON 数组，包含子 SKU id 与可选数量
    valid_days = Column(Integer, default=365)  # 购买后有效天数
    status = Column(String(20), default="on_sale")  # 上架状态


class MaCompetitorPrice(Base):
    """竞品采价：市场调研，辅助定价与话术。"""

    __tablename__ = "ma_competitor_price"  # 竞品价格采集表
    id = Column(Integer, primary_key=True)  # 主键
    competitor_name = Column(String(64))  # 竞品机构或品牌名
    city = Column(String(64))  # 采样城市
    project_name = Column(String(128))  # 对标项目名称
    price_low = Column(Numeric(12, 2))  # 调研低价区间
    price_high = Column(Numeric(12, 2))  # 调研高价区间
    sampled_at = Column(Date)  # 采样日期


# ---------------------------------------------------------------------------
# 方案与订单：治疗方案、报价、订单行、合同、定金台账
# ---------------------------------------------------------------------------


class MaTreatmentPlan(Base):
    """治疗方案：面诊后结构化方案，含整单折扣前金额。"""

    __tablename__ = "ma_treatment_plan"  # 治疗方案主表
    id = Column(Integer, primary_key=True)  # 主键
    plan_no = Column(String(32), unique=True)  # 方案单号
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    consultation_id = Column(Integer, ForeignKey("ma_consultation.id"), nullable=True)  # 来源咨询单
    consultant_emp_id = Column(Integer, ForeignKey("ma_employee.id"))  # 出具方案的咨询师
    total_list_amount = Column(Numeric(12, 2))  # 明细原价合计
    discount_amount = Column(Numeric(12, 2), default=0)  # 整单减免金额
    status = Column(String(32), default="draft")  # draft / confirmed / void 等
    created_at = Column(DateTime, default=datetime.now)  # 方案创建时间


class MaTreatmentPlanLine(Base):
    """治疗方案明细行：SKU、数量、单价与小计。"""

    __tablename__ = "ma_treatment_plan_line"  # 治疗方案明细表
    id = Column(Integer, primary_key=True)  # 主键
    plan_id = Column(Integer, ForeignKey("ma_treatment_plan.id"), index=True)  # 所属方案
    sku_id = Column(Integer, ForeignKey("ma_product_sku.id"))  # 品项
    qty = Column(Integer, default=1)  # 数量
    unit_price = Column(Numeric(12, 2))  # 行内执行单价
    line_amount = Column(Numeric(12, 2))  # 行小计 = qty * unit_price（业务可再调）


class MaQuotation(Base):
    """报价单：对客户正式报价，含有效期与状态。"""

    __tablename__ = "ma_quotation"  # 报价单表
    id = Column(Integer, primary_key=True)  # 主键
    quote_no = Column(String(32), unique=True)  # 报价单号
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    plan_id = Column(Integer, ForeignKey("ma_treatment_plan.id"), nullable=True)  # 关联方案，口头报价可空
    sales_id = Column(Integer, ForeignKey("ma_salesperson.id"))  # 报价责任人
    amount = Column(Numeric(12, 2))  # 报价总金额
    valid_until = Column(Date)  # 报价有效截止日
    status = Column(String(32), default="sent")  # sent / accepted / expired 等
    created_at = Column(DateTime, default=datetime.now)  # 出具时间


class MaOrder(Base):
    """销售订单：总金额、已付、状态，可关联商机。"""

    __tablename__ = "ma_order"  # 订单主表
    id = Column(Integer, primary_key=True)  # 主键
    order_no = Column(String(32), unique=True)  # 订单号
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 开单分院
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    sales_id = Column(Integer, ForeignKey("ma_salesperson.id"))  # 主销售
    opp_id = Column(Integer, ForeignKey("ma_opportunity.id"), nullable=True)  # 来源商机
    order_type = Column(String(32), default="service")  # service 服务单 / product 实物等
    total_amount = Column(Numeric(12, 2))  # 应收总额
    paid_amount = Column(Numeric(12, 2), default=0)  # 已付累计
    order_status = Column(String(32), default="pending_pay")  # 待付/已付/部分退款等
    ordered_at = Column(DateTime, default=datetime.now)  # 下单时间


class MaOrderLine(Base):
    """订单明细：SKU 或套餐行，含分摊折扣与行金额。"""

    __tablename__ = "ma_order_line"  # 订单明细表
    id = Column(Integer, primary_key=True)  # 主键
    order_id = Column(Integer, ForeignKey("ma_order.id"), index=True)  # 所属订单
    sku_id = Column(Integer, ForeignKey("ma_product_sku.id"))  # 品项 SKU
    bundle_id = Column(Integer, ForeignKey("ma_package_bundle.id"), nullable=True)  # 若来自套餐则填套餐 id
    qty = Column(Integer, default=1)  # 数量
    unit_price = Column(Numeric(12, 2))  # 折前或标价单价，以业务约定为准
    discount_share = Column(Numeric(12, 2), default=0)  # 整单优惠分摊到本行金额
    line_amount = Column(Numeric(12, 2))  # 行实付或应收净值


class MaContract(Base):
    """电子/纸质合同：模板、签署时间、PDF 存储地址。"""

    __tablename__ = "ma_contract"  # 合同表
    id = Column(Integer, primary_key=True)  # 主键
    contract_no = Column(String(32), unique=True)  # 合同编号
    order_id = Column(Integer, ForeignKey("ma_order.id"), index=True)  # 关联订单
    customer_id = Column(Integer, ForeignKey("ma_customer.id"))  # 签约客户
    template_code = Column(String(32))  # 使用的合同模板编码
    signed_at = Column(DateTime, nullable=True)  # 实际签署时间，未签可空
    pdf_url = Column(String(512), nullable=True)  # 归档 PDF 路径或 URL
    status = Column(String(32), default="draft")  # draft / signed / void 等


class MaDepositLedger(Base):
    """定金台账：每笔收退与客户、订单关联，便于对账。"""

    __tablename__ = "ma_deposit_ledger"  # 定金流水表
    id = Column(Integer, primary_key=True)  # 主键
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    order_id = Column(Integer, ForeignKey("ma_order.id"), nullable=True)  # 关联订单，预存可空
    amount = Column(Numeric(12, 2))  # 金额，正为收负为退由 direction 表达或业务约定
    direction = Column(String(16))  # in 收入 / out 支出 等
    reason = Column(String(128))  # 摘要：定金/转尾款/退定等
    created_at = Column(DateTime, default=datetime.now)  # 记账时间


# ---------------------------------------------------------------------------
# 支付与会员：支付、退款、分期、会员卡、积分、优惠券、满赠
# ---------------------------------------------------------------------------


class MaPayment(Base):
    """收款流水：渠道、第三方单号、状态。"""

    __tablename__ = "ma_payment"  # 支付记录表
    id = Column(Integer, primary_key=True)  # 主键
    pay_no = Column(String(48), unique=True)  # 内部支付流水号
    order_id = Column(Integer, ForeignKey("ma_order.id"), index=True)  # 关联订单
    pay_channel = Column(String(32))  # wechat_native / alipay / pos 等
    amount = Column(Numeric(12, 2))  # 实付金额
    pay_time = Column(DateTime, default=datetime.now)  # 支付成功时间
    third_trade_no = Column(String(128), nullable=True)  # 微信/支付宝交易号
    status = Column(String(20), default="success")  # success / pending / failed 等


class MaRefund(Base):
    """退款申请与结果：审批人、原因、状态。"""

    __tablename__ = "ma_refund"  # 退款表
    id = Column(Integer, primary_key=True)  # 主键
    refund_no = Column(String(48), unique=True)  # 退款单号
    order_id = Column(Integer, ForeignKey("ma_order.id"), index=True)  # 原订单
    payment_id = Column(Integer, ForeignKey("ma_payment.id"), nullable=True)  # 原支付流水，可空
    amount = Column(Numeric(12, 2))  # 退款金额
    reason = Column(String(256))  # 退款原因说明
    approved_by_emp_id = Column(Integer, ForeignKey("ma_employee.id"), nullable=True)  # 审批人
    status = Column(String(32), default="pending")  # pending / approved / rejected / done 等
    created_at = Column(DateTime, default=datetime.now)  # 申请时间


class MaInstallmentPlan(Base):
    """分期方案：与订单一对一，首付、月供、合作金融机构。"""

    __tablename__ = "ma_installment_plan"  # 分期主表
    id = Column(Integer, primary_key=True)  # 主键
    order_id = Column(Integer, ForeignKey("ma_order.id"), unique=True)  # 一单一分期
    total_terms = Column(Integer)  # 总期数
    down_payment = Column(Numeric(12, 2))  # 首付金额
    monthly_amount = Column(Numeric(12, 2))  # 每期应还（等额简化场景）
    finance_partner = Column(String(64), nullable=True)  # 分期合作方名称
    status = Column(String(32), default="active")  # active / settled / defaulted 等


class MaInstallmentSchedule(Base):
    """分期还款计划表：每期应还日、实还时间、状态。"""

    __tablename__ = "ma_installment_schedule"  # 分期期次明细表
    id = Column(Integer, primary_key=True)  # 主键
    plan_id = Column(Integer, ForeignKey("ma_installment_plan.id"), index=True)  # 所属分期方案
    term_no = Column(Integer)  # 第几期，从 1 起
    due_date = Column(Date)  # 应还日期
    amount = Column(Numeric(12, 2))  # 本期应还金额
    paid_at = Column(DateTime, nullable=True)  # 实际还清时间
    status = Column(String(20), default="due")  # due / paid / overdue 等


class MaMemberCard(Base):
    """会员卡：等级、储值余额、积分余额、开卡日。"""

    __tablename__ = "ma_member_card"  # 会员卡表
    id = Column(Integer, primary_key=True)  # 主键
    card_no = Column(String(32), unique=True)  # 卡号
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), unique=True)  # 一客户一卡简化模型
    tier = Column(String(32))  # 卡等级
    balance = Column(Numeric(12, 2), default=0)  # 储值余额，元
    points_balance = Column(Integer, default=0)  # 当前可用积分
    opened_at = Column(Date, default=date.today)  # 开卡日期，默认当天


class MaPointsLedger(Base):
    """积分流水：每笔增减、业务类型、关联订单。"""

    __tablename__ = "ma_points_ledger"  # 积分流水表
    id = Column(Integer, primary_key=True)  # 主键
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    change_points = Column(Integer)  # 变动积分，可正可负
    biz_type = Column(String(32))  # consume_reward / redeem / adjust 等
    ref_order_id = Column(Integer, ForeignKey("ma_order.id"), nullable=True)  # 关联订单
    created_at = Column(DateTime, default=datetime.now)  # 记账时间


class MaCouponTemplate(Base):
    """优惠券模板：满减规则、面值类型、最低消费与有效天数。"""

    __tablename__ = "ma_coupon_template"  # 券模板表
    id = Column(Integer, primary_key=True)  # 主键
    code = Column(String(32), unique=True)  # 模板编码
    name = Column(String(128))  # 模板名称，C 端展示
    discount_type = Column(String(16))  # fixed 固定额 / percent 折扣率等
    discount_value = Column(Numeric(12, 2))  # 面额或折扣值，含义随 discount_type
    min_spend = Column(Numeric(12, 2), default=0)  # 最低订单金额门槛
    valid_days = Column(Integer, default=30)  # 领券后有效天数


class MaCouponIssue(Base):
    """发券实例：一券一码、使用状态、核销订单。"""

    __tablename__ = "ma_coupon_issue"  # 已发优惠券表
    id = Column(Integer, primary_key=True)  # 主键
    template_id = Column(Integer, ForeignKey("ma_coupon_template.id"), index=True)  # 模板
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 领取人
    coupon_code = Column(String(48), unique=True)  # 唯一券码，核销扫码用
    status = Column(String(20), default="unused")  # unused / used / expired 等
    issued_at = Column(DateTime, default=datetime.now)  # 发放时间
    used_order_id = Column(Integer, ForeignKey("ma_order.id"), nullable=True)  # 核销订单


class MaGiftWithPurchase(Base):
    """满赠记录：订单维度的赠品发放，便于库存与成本核算。"""

    __tablename__ = "ma_gift_with_purchase"  # 满赠明细表
    id = Column(Integer, primary_key=True)  # 主键
    order_id = Column(Integer, ForeignKey("ma_order.id"), index=True)  # 触发订单
    gift_sku_id = Column(Integer, ForeignKey("ma_product_sku.id"))  # 赠品对应 SKU（可为虚拟项）
    qty = Column(Integer, default=1)  # 赠品数量
    campaign_code = Column(String(32))  # 活动编码，与营销 campaign 对齐


# ---------------------------------------------------------------------------
# 提成与目标：规则、销售提成明细、医生分润、目标、日统计
# ---------------------------------------------------------------------------


class MaCommissionRule(Base):
    """提成规则：按分院+品项分类+比例+生效区间。"""

    __tablename__ = "ma_commission_rule"  # 提成规则表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 适用分院
    rule_name = Column(String(128))  # 规则名称，便于运营识别
    sku_category_id = Column(Integer, ForeignKey("ma_product_category.id"), nullable=True)  # 空表示全场默认
    rate_pct = Column(Numeric(6, 3))  # 提成比例，百分比数值如 5.000 表示 5%
    effective_from = Column(Date)  # 规则生效起
    effective_to = Column(Date, nullable=True)  # 规则生效止，空表示未失效


class MaCommissionDetail(Base):
    """销售提成明细：按订单/销售/SKU 拆账，归属结算月。"""

    __tablename__ = "ma_commission_detail"  # 提成明细表
    id = Column(Integer, primary_key=True)  # 主键
    order_id = Column(Integer, ForeignKey("ma_order.id"), index=True)  # 来源订单
    sales_id = Column(Integer, ForeignKey("ma_salesperson.id"), index=True)  # 拿提成销售
    sku_id = Column(Integer, ForeignKey("ma_product_sku.id"), nullable=True)  # 拆到品项，整单奖可空
    base_amount = Column(Numeric(12, 2))  # 提成计提基数
    commission_amount = Column(Numeric(12, 2))  # 应发提成金额
    settlement_month = Column(String(7))  # 归属结算月，格式 YYYY-MM
    status = Column(String(20), default="accrued")  # accrued 已计提 / paid 已发放 等


class MaDoctorCommissionSplit(Base):
    """医生分润：按订单行拆给执行医生，比例+金额落库。"""

    __tablename__ = "ma_doctor_commission_split"  # 医生分润表
    id = Column(Integer, primary_key=True)  # 主键
    order_line_id = Column(Integer, ForeignKey("ma_order_line.id"), index=True)  # 订单行
    doctor_emp_id = Column(Integer, ForeignKey("ma_employee.id"))  # 医生员工
    split_pct = Column(Numeric(6, 3))  # 分润占比
    amount = Column(Numeric(12, 2))  # 分润金额


class MaSalesTarget(Base):
    """销售个人目标：按月营收与可选单量目标。"""

    __tablename__ = "ma_sales_target"  # 销售目标表
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 分院
    sales_id = Column(Integer, ForeignKey("ma_salesperson.id"), index=True)  # 销售
    target_month = Column(String(7), index=True)  # 目标月份 YYYY-MM
    revenue_target = Column(Numeric(14, 2))  # 营收目标金额
    deal_count_target = Column(Integer, nullable=True)  # 成交单数目标，可空


class MaDailySalesStat(Base):
    """分院日统计：线索、预约、到院、订单数与营收汇总。"""

    __tablename__ = "ma_daily_sales_stat"  # 日销售统计表（预聚合）
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 分院
    stat_date = Column(Date, index=True)  # 统计日期
    new_leads = Column(Integer, default=0)  # 当日新增线索数
    appt_count = Column(Integer, default=0)  # 当日预约数
    visit_count = Column(Integer, default=0)  # 当日到院人次
    order_count = Column(Integer, default=0)  # 当日成交订单数
    revenue = Column(Numeric(14, 2), default=0)  # 当日确认营收


# ---------------------------------------------------------------------------
# 渠道与营销：渠道商、结算、活动、报名、老带新奖励
# ---------------------------------------------------------------------------


class MaChannelPartner(Base):
    """渠道合作方：医美转诊、异业、KOL 等，含联系人及返利 JSON 策略。"""

    __tablename__ = "ma_channel_partner"  # 渠道伙伴表
    id = Column(Integer, primary_key=True)  # 主键
    partner_code = Column(String(32), unique=True)  # 渠道编码
    name = Column(String(128))  # 渠道全称
    partner_type = Column(String(32))  # 类型：referral / koc / enterprise 等
    contact_name = Column(String(64))  # 对接人姓名
    contact_phone = Column(String(20))  # 对接人手机
    rebate_policy_json = Column(Text)  # 返利阶梯 JSON，结构由业务解析
    status = Column(String(20), default="active")  # 合作状态


class MaChannelSettlement(Base):
    """渠道月度结算：线索量、成交量、结算金额与状态。"""

    __tablename__ = "ma_channel_settlement"  # 渠道结算单表
    id = Column(Integer, primary_key=True)  # 主键
    partner_id = Column(Integer, ForeignKey("ma_channel_partner.id"), index=True)  # 渠道
    period_month = Column(String(7), index=True)  # 结算月 YYYY-MM
    lead_count = Column(Integer, default=0)  # 周期内确认线索数
    deal_count = Column(Integer, default=0)  # 周期内成交笔数
    settlement_amount = Column(Numeric(14, 2), default=0)  # 应结金额
    status = Column(String(32), default="draft")  # draft / confirmed / paid 等


class MaMarketingCampaign(Base):
    """营销活动：时间窗、预算、UTM 来源标记。"""

    __tablename__ = "ma_marketing_campaign"  # 营销活动表
    id = Column(Integer, primary_key=True)  # 主键
    campaign_code = Column(String(32), unique=True)  # 活动编码
    name = Column(String(128))  # 活动名称
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), nullable=True)  # 分院专场可填，全集团可空
    start_at = Column(DateTime)  # 活动开始时间
    end_at = Column(DateTime)  # 活动结束时间
    budget = Column(Numeric(14, 2), nullable=True)  # 活动预算金额
    utm_source = Column(String(64), nullable=True)  # 投放追踪 utm_source


class MaCampaignEnrollment(Base):
    """活动报名：客户参与记录，用于到院礼与短信触达。"""

    __tablename__ = "ma_campaign_enrollment"  # 活动报名表
    id = Column(Integer, primary_key=True)  # 主键
    campaign_id = Column(Integer, ForeignKey("ma_marketing_campaign.id"), index=True)  # 活动
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    enrolled_at = Column(DateTime, default=datetime.now)  # 报名时间


class MaReferralReward(Base):
    """老带新奖励：推荐人、被推荐人、关联订单与积分/现金奖励。"""

    __tablename__ = "ma_referral_reward"  # 转介绍奖励表
    id = Column(Integer, primary_key=True)  # 主键
    referrer_customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 推荐人客户 id
    referee_customer_id = Column(Integer, ForeignKey("ma_customer.id"))  # 被推荐人客户 id
    order_id = Column(Integer, ForeignKey("ma_order.id"), nullable=True)  # 触发奖励的订单
    reward_points = Column(Integer, default=0)  # 奖励积分
    reward_cash = Column(Numeric(12, 2), default=0)  # 奖励现金或储值
    status = Column(String(20), default="pending")  # pending / granted / void 等


# ---------------------------------------------------------------------------
# 售后与运营：回访任务、NPS、投诉工单
# ---------------------------------------------------------------------------


class MaAftercareTask(Base):
    """术后回访任务：类型、截止时间、执行人、完成状态。"""

    __tablename__ = "ma_aftercare_task"  # 回访任务表
    id = Column(Integer, primary_key=True)  # 主键
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    order_id = Column(Integer, ForeignKey("ma_order.id"), nullable=True)  # 关联订单/治疗
    task_type = Column(String(32))  # day1 / day7 / month1 等随访类型
    due_at = Column(DateTime)  # 任务截止时间
    assign_emp_id = Column(Integer, ForeignKey("ma_employee.id"))  # 执行人
    status = Column(String(20), default="open")  # open / done / overdue 等


class MaSatisfactionSurvey(Base):
    """满意度与 NPS：可关联到院记录，收集评论。"""

    __tablename__ = "ma_satisfaction_survey"  # 满意度调研表
    id = Column(Integer, primary_key=True)  # 主键
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    visit_id = Column(Integer, ForeignKey("ma_visit_record.id"), nullable=True)  # 关联到院，可空
    nps_score = Column(Integer)  # 0–10 净推荐值打分
    comment = Column(Text, nullable=True)  # 文字反馈
    submitted_at = Column(DateTime, default=datetime.now)  # 提交时间


class MaComplaintTicket(Base):
    """投诉工单：分类、描述、责任人、处理状态。"""

    __tablename__ = "ma_complaint_ticket"  # 投诉工单表
    id = Column(Integer, primary_key=True)  # 主键
    ticket_no = Column(String(32), unique=True)  # 工单号
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 投诉人客户
    order_id = Column(Integer, ForeignKey("ma_order.id"), nullable=True)  # 关联订单
    category = Column(String(64))  # 投诉大类：服务/效果/收费等
    description = Column(Text)  # 详细描述
    owner_emp_id = Column(Integer, ForeignKey("ma_employee.id"))  # 当前处理人
    status = Column(String(32), default="open")  # open / investigating / closed 等
    created_at = Column(DateTime, default=datetime.now)  # 建单时间


# ---------------------------------------------------------------------------
# 标签与库存：客户标签字典、客户-标签关系、耗材批次
# ---------------------------------------------------------------------------


class MaCustomerTag(Base):
    """客户标签字典：编码、名称、分组（销售/医学等）。"""

    __tablename__ = "ma_customer_tag"  # 标签维表
    id = Column(Integer, primary_key=True)  # 主键
    tag_code = Column(String(32), unique=True)  # 标签编码
    tag_name = Column(String(64))  # 标签展示名
    tag_group = Column(String(32))  # 标签分组，筛选器分组用


class MaCustomerTagRel(Base):
    """客户与标签多对多：打标时间与客户、标签外键。"""

    __tablename__ = "ma_customer_tag_rel"  # 客户标签关联表
    id = Column(Integer, primary_key=True)  # 主键
    customer_id = Column(Integer, ForeignKey("ma_customer.id"), index=True)  # 客户
    tag_id = Column(Integer, ForeignKey("ma_customer_tag.id"), index=True)  # 标签
    created_at = Column(DateTime, default=datetime.now)  # 打标时间


class MaInventoryBatch(Base):
    """耗材/药品批次：分院库存、批号、效期、数量与单位成本。"""

    __tablename__ = "ma_inventory_batch"  # 库存批次表（简化）
    id = Column(Integer, primary_key=True)  # 主键
    branch_id = Column(Integer, ForeignKey("ma_branch.id"), index=True)  # 所在分院库房
    sku_id = Column(Integer, ForeignKey("ma_product_sku.id"), nullable=True)  # 对应可售卖 SKU，纯耗材可空
    material_name = Column(String(128))  # 物料名称，如某品牌玻尿酸
    batch_no = Column(String(64))  # 厂商批号
    qty = Column(Integer)  # 当前剩余数量
    expiry_date = Column(Date, nullable=True)  # 有效期至
    unit_cost = Column(Numeric(12, 4), nullable=True)  # 单位成本，四位小数适配低单价耗材
