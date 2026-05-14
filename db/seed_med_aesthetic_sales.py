"""
医美销售演示数据：首次全量 seed + 每次启动对空表 topup，保证 ma_* 均有数据。
用法：python -m db.seed_med_aesthetic_sales
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select, text

from .base import SessionLocal, engine
from .med_aesthetic_sales_models import (
    MaAftercareTask,
    MaAppointment,
    MaBranch,
    MaCampaignEnrollment,
    MaChannelPartner,
    MaChannelSettlement,
    MaCommissionDetail,
    MaCommissionRule,
    MaCompetitorPrice,
    MaComplaintTicket,
    MaConsultantSchedule,
    MaConsultation,
    MaContract,
    MaCouponIssue,
    MaCouponTemplate,
    MaCustomer,
    MaCustomerProfile,
    MaCustomerTag,
    MaCustomerTagRel,
    MaDailySalesStat,
    MaDepositLedger,
    MaDepartment,
    MaDoctorCommissionSplit,
    MaEmployee,
    MaGiftWithPurchase,
    MaInstallmentPlan,
    MaInstallmentSchedule,
    MaInventoryBatch,
    MaLead,
    MaLeadFollowup,
    MaLeadSource,
    MaMarketingCampaign,
    MaMemberCard,
    MaOpportunity,
    MaOrder,
    MaOrderLine,
    MaOrganization,
    MaPackageBundle,
    MaPayment,
    MaPointsLedger,
    MaPriceListItem,
    MaPriceListVersion,
    MaProductCategory,
    MaProductSku,
    MaQuotation,
    MaReferralReward,
    MaRefund,
    MaSalesperson,
    MaSalesPipelineStage,
    MaSalesTarget,
    MaSalesTeam,
    MaSatisfactionSurvey,
    MaTreatmentPlan,
    MaTreatmentPlanLine,
    MaVisitRecord,
)


def _count(session, model) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def topup_ma_empty_tables() -> int:
    """
    已有集团数据但部分 ma_* 表为空时（例如旧版 seed），按现有主数据补行。
    返回本次实际执行了「补数据」的表数量（仅统计本函数内处理的表）。
    """
    db = SessionLocal()
    filled_tables = 0
    try:
        if _count(db, MaOrganization) == 0:
            return 0

        branch = db.scalars(select(MaBranch).order_by(MaBranch.id)).first()
        emp = db.scalars(select(MaEmployee).order_by(MaEmployee.id)).first()
        cust = db.scalars(select(MaCustomer).order_by(MaCustomer.id)).first()
        cust2 = db.scalars(select(MaCustomer).order_by(MaCustomer.id).offset(1)).first()
        order0 = db.scalars(select(MaOrder).order_by(MaOrder.id)).first()
        pay0 = db.scalars(select(MaPayment).order_by(MaPayment.id)).first()
        visit0 = db.scalars(select(MaVisitRecord).order_by(MaVisitRecord.id)).first()
        sku0 = db.scalars(select(MaProductSku).order_by(MaProductSku.id)).first()
        ol0 = db.scalars(select(MaOrderLine).order_by(MaOrderLine.id)).first()
        camp0 = db.scalars(select(MaMarketingCampaign).order_by(MaMarketingCampaign.id)).first()
        sp0 = db.scalars(select(MaSalesperson).order_by(MaSalesperson.id)).first()
        cat0 = db.scalars(select(MaProductCategory).order_by(MaProductCategory.id)).first()
        doc = db.scalars(
            select(MaEmployee).where(MaEmployee.job_title.contains("医生")).limit(1)
        ).first() or emp

        def bump() -> None:
            nonlocal filled_tables
            filled_tables += 1

        if branch is None or emp is None:
            db.commit()
            return 0

        if _count(db, MaPackageBundle) == 0 and sku0:
            db.add(
                MaPackageBundle(
                    bundle_code="PKG-TOPUP-01",
                    name="补水紧致体验包",
                    bundle_price=9800,
                    sku_ids_json=f"[{sku0.id}]",
                    valid_days=180,
                )
            )
            bump()

        if _count(db, MaCompetitorPrice) == 0:
            db.add_all(
                [
                    MaCompetitorPrice(
                        competitor_name="某颜医美",
                        city="上海",
                        project_name="超声炮全面部",
                        price_low=9800,
                        price_high=15800,
                        sampled_at=date(2026, 5, 1),
                    ),
                    MaCompetitorPrice(
                        competitor_name="轻医美工作室",
                        city="上海",
                        project_name="基础水光",
                        price_low=399,
                        price_high=899,
                        sampled_at=date(2026, 5, 2),
                    ),
                ]
            )
            bump()

        if _count(db, MaChannelPartner) == 0:
            p = MaChannelPartner(
                partner_code="CH-TOPUP-01",
                name="美业转诊联盟A",
                partner_type="referral",
                contact_name="赵渠道",
                contact_phone="13600000001",
                rebate_policy_json='{"per_deal": 800, "cap_month": 50000}',
            )
            db.add(p)
            db.flush()
            bump()

        if _count(db, MaChannelSettlement) == 0:
            p_any = db.scalars(select(MaChannelPartner).order_by(MaChannelPartner.id)).first()
            if p_any:
                db.add(
                    MaChannelSettlement(
                        partner_id=p_any.id,
                        period_month="2026-04",
                        lead_count=45,
                        deal_count=6,
                        settlement_amount=12800,
                        status="confirmed",
                    )
                )
                bump()

        if _count(db, MaConsultantSchedule) == 0:
            db.add(
                MaConsultantSchedule(
                    branch_id=branch.id,
                    emp_id=emp.id,
                    work_date=date.today(),
                    slot_start="09:00",
                    slot_end="18:00",
                    max_appts=10,
                )
            )
            bump()

        if _count(db, MaCommissionRule) == 0:
            db.add(
                MaCommissionRule(
                    branch_id=branch.id,
                    rule_name="注射类默认提成",
                    sku_category_id=cat0.id if cat0 else None,
                    rate_pct=5,
                    effective_from=date(2026, 1, 1),
                )
            )
            bump()

        if cust and order0 and _count(db, MaContract) == 0:
            db.add(
                MaContract(
                    contract_no="CT-TOPUP-01",
                    order_id=order0.id,
                    customer_id=cust.id,
                    template_code="SVC-2026",
                    signed_at=datetime.now() - timedelta(days=2),
                    status="signed",
                )
            )
            bump()

        if cust and _count(db, MaDepositLedger) == 0:
            db.add_all(
                [
                    MaDepositLedger(
                        customer_id=cust.id,
                        order_id=order0.id if order0 else None,
                        amount=2000,
                        direction="in",
                        reason="预约金",
                    ),
                    MaDepositLedger(
                        customer_id=cust.id,
                        order_id=order0.id if order0 else None,
                        amount=500,
                        direction="out",
                        reason="转尾款抵扣",
                    ),
                ]
            )
            bump()

        if order0 and pay0 and _count(db, MaRefund) == 0:
            db.add(
                MaRefund(
                    refund_no="RF-TOPUP-01",
                    order_id=order0.id,
                    payment_id=pay0.id,
                    amount=500,
                    reason="活动差价退还",
                    status="approved",
                )
            )
            bump()

        subq_install_orders = select(MaInstallmentPlan.order_id)
        order_no_install = db.scalars(
            select(MaOrder).where(MaOrder.id.not_in(subq_install_orders)).limit(1)
        ).first()
        if order_no_install and _count(db, MaInstallmentPlan) == 0:
            pl = MaInstallmentPlan(
                order_id=order_no_install.id,
                total_terms=6,
                down_payment=3000,
                monthly_amount=1500,
                finance_partner="演示消费金融",
                status="active",
            )
            db.add(pl)
            db.flush()
            bump()
            if _count(db, MaInstallmentSchedule) == 0:
                for i in range(1, 7):
                    db.add(
                        MaInstallmentSchedule(
                            plan_id=pl.id,
                            term_no=i,
                            due_date=date(2026, 6, 1) + timedelta(days=30 * (i - 1)),
                            amount=1500,
                            paid_at=datetime.now() if i == 1 else None,
                            status="paid" if i == 1 else "due",
                        )
                    )
                bump()

        if order0 and sku0 and _count(db, MaGiftWithPurchase) == 0:
            db.add(
                MaGiftWithPurchase(
                    order_id=order0.id,
                    gift_sku_id=sku0.id,
                    qty=1,
                    campaign_code="GWP-DEMO",
                )
            )
            bump()

        if ol0 and doc and _count(db, MaDoctorCommissionSplit) == 0:
            db.add(
                MaDoctorCommissionSplit(
                    order_line_id=ol0.id,
                    doctor_emp_id=doc.id,
                    split_pct=12,
                    amount=500,
                )
            )
            bump()

        if camp0 and cust and _count(db, MaCampaignEnrollment) == 0:
            db.add(
                MaCampaignEnrollment(
                    campaign_id=camp0.id,
                    customer_id=cust.id,
                )
            )
            bump()

        if cust and cust2 and _count(db, MaReferralReward) == 0:
            db.add(
                MaReferralReward(
                    referrer_customer_id=cust.id,
                    referee_customer_id=cust2.id,
                    order_id=order0.id if order0 else None,
                    reward_points=500,
                    reward_cash=200,
                    status="granted",
                )
            )
            bump()

        if cust and emp and _count(db, MaAftercareTask) == 0:
            db.add(
                MaAftercareTask(
                    customer_id=cust.id,
                    order_id=order0.id if order0 else None,
                    task_type="day7_call",
                    due_at=datetime.now() + timedelta(days=5),
                    assign_emp_id=emp.id,
                    status="open",
                )
            )
            bump()

        if cust and visit0 and _count(db, MaSatisfactionSurvey) == 0:
            db.add(
                MaSatisfactionSurvey(
                    customer_id=cust.id,
                    visit_id=visit0.id,
                    nps_score=9,
                    comment="环境不错，等待略久",
                )
            )
            bump()

        if cust and emp and _count(db, MaComplaintTicket) == 0:
            db.add(
                MaComplaintTicket(
                    ticket_no="TK-TOPUP-01",
                    customer_id=cust.id,
                    order_id=order0.id if order0 else None,
                    category="服务流程",
                    description="前台登记信息与系统不一致，已当场更正",
                    owner_emp_id=emp.id,
                    status="closed",
                )
            )
            bump()

        if branch and _count(db, MaInventoryBatch) == 0:
            db.add(
                MaInventoryBatch(
                    branch_id=branch.id,
                    sku_id=sku0.id if sku0 else None,
                    material_name="透明质酸钠凝胶（演示批次）",
                    batch_no="BATCH-DEMO-001",
                    qty=120,
                    expiry_date=date(2027, 12, 31),
                    unit_cost=420.5,
                )
            )
            bump()

        db.commit()
        return filled_tables
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seed_if_empty() -> bool:
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM ma_organization")).scalar_one()
        if n and n > 0:
            return False

    db = SessionLocal()
    try:
        org = MaOrganization(
            name="臻美医疗美容集团",
            legal_name="臻美医疗美容管理有限公司",
            license_no="PDY123456789",
            city="上海",
        )
        db.add(org)
        db.flush()

        b1 = MaBranch(
            org_id=org.id,
            branch_code="SH-XH-01",
            name="臻美·徐汇旗舰院",
            address="上海市徐汇区淮海中路188号3层",
            phone="021-63001234",
            opened_at=date(2021, 6, 1),
        )
        b2 = MaBranch(
            org_id=org.id,
            branch_code="SH-PD-02",
            name="臻美·浦东分院",
            address="上海市浦东新区世纪大道100号2层",
            phone="021-58881234",
            opened_at=date(2023, 3, 15),
        )
        db.add_all([b1, b2])
        db.flush()

        d_sales = MaDepartment(
            branch_id=b1.id, name="销售中心", dept_type="sales", parent_id=None
        )
        d_cons = MaDepartment(
            branch_id=b1.id, name="咨询部", dept_type="consult", parent_id=None
        )
        d_nurse = MaDepartment(
            branch_id=b1.id, name="护理部", dept_type="nurse", parent_id=None
        )
        db.add_all([d_sales, d_cons, d_nurse])
        db.flush()

        e1 = MaEmployee(
            branch_id=b1.id,
            emp_no="E2023001",
            name="李婉清",
            mobile="13800001111",
            job_title="资深医美咨询师",
            hire_date=date(2023, 3, 1),
        )
        e2 = MaEmployee(
            branch_id=b1.id,
            emp_no="E2022015",
            name="周晨",
            mobile="13800002222",
            job_title="网电销售主管",
            hire_date=date(2022, 8, 15),
        )
        e3 = MaEmployee(
            branch_id=b1.id,
            emp_no="E2024002",
            name="王医生",
            mobile="13800003333",
            job_title="皮肤科主治医师",
            hire_date=date(2024, 1, 8),
        )
        e4 = MaEmployee(
            branch_id=b1.id,
            emp_no="E2024108",
            name="陈前台",
            mobile="13800004444",
            job_title="前台接待",
            hire_date=date(2024, 6, 1),
        )
        e5 = MaEmployee(
            branch_id=b1.id,
            emp_no="E2023501",
            name="刘网咨",
            mobile="13800005555",
            job_title="网电咨询师",
            hire_date=date(2023, 11, 20),
        )
        e6 = MaEmployee(
            branch_id=b2.id,
            emp_no="E2025001",
            name="赵销售",
            mobile="13800006666",
            job_title="现场咨询",
            hire_date=date(2025, 2, 10),
        )
        db.add_all([e1, e2, e3, e4, e5, e6])
        db.flush()

        team1 = MaSalesTeam(
            branch_id=b1.id, team_name="徐汇网咨一组", leader_emp_id=e2.id
        )
        team2 = MaSalesTeam(
            branch_id=b2.id, team_name="浦东现场组", leader_emp_id=e6.id
        )
        db.add_all([team1, team2])
        db.flush()

        sp1 = MaSalesperson(
            employee_id=e2.id,
            team_id=team1.id,
            level_code="L2",
            wecom_id="zhouchen_wm",
            monthly_quota=800000,
        )
        sp2 = MaSalesperson(
            employee_id=e6.id,
            team_id=team2.id,
            level_code="L1",
            wecom_id="zhao_xs_wm",
            monthly_quota=500000,
        )
        db.add_all([sp1, sp2])
        db.flush()

        src_xhs = MaLeadSource(
            code="XHS_AD", name="小红书信息流", channel_type="paid_social", cost_per_lead=120
        )
        src_ref = MaLeadSource(
            code="REFERRAL", name="老客转介绍", channel_type="referral", cost_per_lead=0
        )
        src_dy = MaLeadSource(
            code="DOUYIN", name="抖音本地推", channel_type="paid_social", cost_per_lead=95
        )
        src_bd = MaLeadSource(
            code="BAIDU", name="百度搜索", channel_type="sem", cost_per_lead=200
        )
        src_wx = MaLeadSource(
            code="WECHAT_MP", name="公众号预约", channel_type="organic", cost_per_lead=0
        )
        db.add_all([src_xhs, src_ref, src_dy, src_bd, src_wx])
        db.flush()

        cat_face = MaProductCategory(parent_id=None, name="面部年轻化", sort_order=1)
        cat_inj = MaProductCategory(parent_id=None, name="注射微整", sort_order=2)
        cat_body = MaProductCategory(parent_id=None, name="身体塑形", sort_order=3)
        db.add_all([cat_face, cat_inj, cat_body])
        db.flush()
        cat_face_sub = MaProductCategory(
            parent_id=cat_face.id, name="光电紧致", sort_order=1
        )
        db.add(cat_face_sub)
        db.flush()

        sku_ulthera = MaProductSku(
            sku_code="SKU-ULTHERA-FACE",
            name="超声炮·全面部（600发）",
            category_id=cat_face.id,
            unit="次",
            list_price=12800,
            cost_price=4200,
            duration_minutes=60,
            device_brand="半岛",
        )
        sku_juvederm = MaProductSku(
            sku_code="SKU-JUVE-1ML",
            name="乔雅登雅致 1ml",
            category_id=cat_inj.id,
            unit="支",
            list_price=6800,
            cost_price=3100,
            duration_minutes=30,
        )
        sku_water = MaProductSku(
            sku_code="SKU-HYDRO-DEEP",
            name="海月兰长效水光（机打）",
            category_id=cat_inj.id,
            unit="次",
            list_price=2980,
            cost_price=900,
            duration_minutes=45,
        )
        sku_photon = MaProductSku(
            sku_code="SKU-M22-FULL",
            name="M22 光子嫩肤全面部",
            category_id=cat_face_sub.id,
            unit="次",
            list_price=2280,
            cost_price=600,
            duration_minutes=40,
            device_brand="科医人",
        )
        sku_cool = MaProductSku(
            sku_code="SKU-COOL-S",
            name="酷塑单点（腹部）",
            category_id=cat_body.id,
            unit="点",
            list_price=8800,
            cost_price=3500,
            duration_minutes=50,
        )
        sku_gift_mask = MaProductSku(
            sku_code="SKU-GIFT-MASK",
            name="术后修护面膜（赠品）",
            category_id=cat_inj.id,
            unit="盒",
            list_price=198,
            cost_price=40,
            duration_minutes=None,
        )
        db.add_all(
            [
                sku_ulthera,
                sku_juvederm,
                sku_water,
                sku_photon,
                sku_cool,
                sku_gift_mask,
            ]
        )
        db.flush()

        pkg_tight = MaPackageBundle(
            bundle_code="PKG-TIGHT-HYDRO",
            name="紧肤补水联合卡",
            bundle_price=13800,
            sku_ids_json=f"[{sku_ulthera.id},{sku_water.id}]",
            valid_days=365,
        )
        pkg_photon3 = MaPackageBundle(
            bundle_code="PKG-PHOTON-3",
            name="光子三次卡",
            bundle_price=5800,
            sku_ids_json=f"[{sku_photon.id},{sku_photon.id},{sku_photon.id}]",
            valid_days=180,
        )
        db.add_all([pkg_tight, pkg_photon3])
        db.flush()

        db.add_all(
            [
                MaCompetitorPrice(
                    competitor_name="某颜医美",
                    city="上海",
                    project_name="超声炮全面部",
                    price_low=9800,
                    price_high=15800,
                    sampled_at=date(2026, 4, 10),
                ),
                MaCompetitorPrice(
                    competitor_name="轻医美工作室",
                    city="上海",
                    project_name="基础水光",
                    price_low=399,
                    price_high=899,
                    sampled_at=date(2026, 4, 12),
                ),
                MaCompetitorPrice(
                    competitor_name="连锁A",
                    city="杭州",
                    project_name="乔雅登1ml",
                    price_low=5200,
                    price_high=7200,
                    sampled_at=date(2026, 4, 20),
                ),
            ]
        )

        plv1 = MaPriceListVersion(
            branch_id=b1.id,
            version_code="PL-2026Q2",
            effective_from=date(2026, 4, 1),
            approved_by_emp_id=e1.id,
        )
        plv2 = MaPriceListVersion(
            branch_id=b2.id,
            version_code="PL-PD-2026Q2",
            effective_from=date(2026, 4, 1),
            effective_to=date(2026, 12, 31),
            approved_by_emp_id=e6.id,
        )
        db.add_all([plv1, plv2])
        db.flush()
        for plv in (plv1, plv2):
            for sku, sp_, mp in (
                (sku_ulthera, 11800, 9800),
                (sku_juvederm, 6800, 5800),
                (sku_water, 2680, 1980),
                (sku_photon, 1980, 1580),
            ):
                db.add(
                    MaPriceListItem(
                        price_list_id=plv.id,
                        sku_id=sku.id,
                        sale_price=sp_,
                        min_price=mp,
                    )
                )

        chn_a = MaChannelPartner(
            partner_code="KOL-001",
            name="美妆博主合作矩阵",
            partner_type="koc",
            contact_name="孙商务",
            contact_phone="13500001111",
            rebate_policy_json='{"cpa": 300, "cps": "8%"}',
        )
        chn_b = MaChannelPartner(
            partner_code="ENT-MEI",
            name="美年大健康异业",
            partner_type="enterprise",
            contact_name="周经理",
            contact_phone="13500002222",
            rebate_policy_json='{"per_lead": 150}',
        )
        db.add_all([chn_a, chn_b])
        db.flush()
        db.add_all(
            [
                MaChannelSettlement(
                    partner_id=chn_a.id,
                    period_month="2026-04",
                    lead_count=120,
                    deal_count=14,
                    settlement_amount=42000,
                    status="paid",
                ),
                MaChannelSettlement(
                    partner_id=chn_b.id,
                    period_month="2026-04",
                    lead_count=80,
                    deal_count=9,
                    settlement_amount=18000,
                    status="confirmed",
                ),
            ]
        )

        rule1 = MaCommissionRule(
            branch_id=b1.id,
            rule_name="光电类默认",
            sku_category_id=cat_face.id,
            rate_pct=4.5,
            effective_from=date(2026, 1, 1),
        )
        rule2 = MaCommissionRule(
            branch_id=b1.id,
            rule_name="注射类默认",
            sku_category_id=cat_inj.id,
            rate_pct=6,
            effective_from=date(2026, 1, 1),
        )
        db.add_all([rule1, rule2])

        customers_data = [
            ("C202605140001", "张小姐", "13912345678", "女", sp1.id, "silver", "小红书"),
            ("C202605140002", "李女士", "13912345679", "女", sp1.id, "normal", "抖音"),
            ("C202605140003", "王总", "13912345680", "男", sp2.id, "gold", "转介绍"),
            ("C202605140004", "赵同学", "13912345681", "女", sp1.id, "normal", "公众号"),
            ("C202605140005", "钱女士", "13912345682", "女", sp1.id, "silver", "小红书"),
            ("C202605140006", "孙小姐", "13912345683", "女", sp2.id, "normal", "百度"),
            ("C202605140007", "周先生", "13912345684", "男", sp2.id, "normal", "地推"),
            ("C202605140008", "吴女士", "13912345685", "女", sp1.id, "platinum", "老客"),
        ]
        custs: list[MaCustomer] = []
        for cno, name, mob, gen, sid, lvl, src in customers_data:
            c = MaCustomer(
                branch_id=b1.id if sid == sp1.id else b2.id,
                customer_no=cno,
                name=name,
                gender=gen,
                birthday=date(1990, 1, 15),
                mobile=mob,
                city="上海",
                first_source=src,
                owner_sales_id=sid,
                member_level=lvl,
            )
            db.add(c)
            custs.append(c)
        db.flush()

        for i, c in enumerate(custs):
            db.add(
                MaCustomerProfile(
                    customer_id=c.id,
                    skin_type=["油性", "干性", "混合偏干", "敏感肌"][i % 4],
                    concern_tags_json=f'["诉求{i % 3}","抗老"]',
                    aesthetic_goal=f"客户{i+1}：紧致/补水/轮廓优化",
                    budget_range=["5千-1万", "1-2万", "2-4万", "4万以上"][i % 4],
                    competitor_brands="竞品A、竞品B",
                )
            )

        tags = [
            MaCustomerTag(tag_code="HIGH_INTENT", tag_name="高意向", tag_group="sales"),
            MaCustomerTag(tag_code="FIRST_INJECT", tag_name="首次注射", tag_group="medical"),
            MaCustomerTag(tag_code="VIP_REFER", tag_name="高净值转介绍源", tag_group="sales"),
            MaCustomerTag(tag_code="PRICE_SENS", tag_name="价格敏感", tag_group="sales"),
        ]
        db.add_all(tags)
        db.flush()
        for ti, c in enumerate(custs):
            db.add(
                MaCustomerTagRel(
                    customer_id=c.id, tag_id=tags[ti % len(tags)].id
                )
            )

        stages = [
            MaSalesPipelineStage(
                branch_id=b1.id,
                stage_code="NEW",
                stage_name="新线索",
                sort_order=1,
                probability_pct=10,
            ),
            MaSalesPipelineStage(
                branch_id=b1.id,
                stage_code="CONTACT",
                stage_name="已触达",
                sort_order=2,
                probability_pct=25,
            ),
            MaSalesPipelineStage(
                branch_id=b1.id,
                stage_code="NEGOTIATION",
                stage_name="方案洽谈",
                sort_order=3,
                probability_pct=55,
            ),
            MaSalesPipelineStage(
                branch_id=b1.id,
                stage_code="CLOSE",
                stage_name="逼单关单",
                sort_order=4,
                probability_pct=80,
            ),
        ]
        db.add_all(stages)
        db.flush()

        leads: list[MaLead] = []
        for i in range(12):
            src = [src_xhs, src_ref, src_dy, src_bd, src_wx][i % 5]
            ld = MaLead(
                branch_id=b1.id,
                lead_no=f"L202605{i+1:04d}",
                name=f"线索客户{i+1}",
                mobile=f"1370000{i:04d}",
                source_id=src.id,
                intent_project=["超声炮", "水光", "光子", "玻尿酸"][i % 4],
                status=["new", "contacted", "converted", "lost"][i % 4],
                score=60 + (i % 35),
                assign_sales_id=sp1.id if i % 2 == 0 else sp2.id,
            )
            db.add(ld)
            leads.append(ld)
        db.flush()

        for ld in leads[:8]:
            for k in range(2):
                db.add(
                    MaLeadFollowup(
                        lead_id=ld.id,
                        sales_id=ld.assign_sales_id,
                        follow_type=["call", "wechat"][k],
                        content=f"第{k+1}次跟进：意向{ld.intent_project}",
                        next_action_at=datetime.now() + timedelta(days=k + 1),
                    )
                )

        cust_main = custs[0]
        lead_main = leads[0]
        st_neg = stages[2]

        opps = []
        for i, c in enumerate(custs[:5]):
            op = MaOpportunity(
                opp_no=f"O202605{i+1:04d}",
                customer_id=c.id,
                lead_id=leads[i].id if i < len(leads) else None,
                stage_id=stages[min(i, 3)].id,
                owner_sales_id=c.owner_sales_id,
                expected_amount=8000 + i * 4000,
                expected_close_date=date(2026, 5, 20) + timedelta(days=i),
                status=["open", "won", "lost", "open", "won"][i],
                lost_reason="对比价格" if i == 2 else None,
            )
            db.add(op)
            opps.append(op)
        db.flush()

        for wd in range(5):
            db.add(
                MaConsultantSchedule(
                    branch_id=b1.id,
                    emp_id=e1.id,
                    work_date=date(2026, 5, 10) + timedelta(days=wd),
                    slot_start="10:00",
                    slot_end="19:00",
                    max_appts=8,
                )
            )
        db.add(
            MaConsultantSchedule(
                branch_id=b2.id,
                emp_id=e6.id,
                work_date=date(2026, 5, 14),
                slot_start="09:30",
                slot_end="18:30",
                max_appts=6,
            )
        )

        for ci, c in enumerate(custs[:6]):
            db.add(
                MaAppointment(
                    branch_id=c.branch_id,
                    customer_id=c.id,
                    project_name=["面诊", "复诊", "治疗"][ci % 3],
                    appt_time=datetime(2026, 5, 8, 10, 0) + timedelta(hours=ci * 2),
                    consultant_emp_id=e1.id,
                    source="网络预约",
                    status=["completed", "booked", "noshow"][ci % 3],
                )
            )
            db.add(
                MaVisitRecord(
                    branch_id=c.branch_id,
                    customer_id=c.id,
                    visit_at=datetime(2026, 5, 8, 9, 30) + timedelta(hours=ci),
                    reception_emp_id=e4.id,
                    first_visit=ci == 0,
                    notes=f"到院记录客户{ci+1}",
                )
            )

        consult_main = MaConsultation(
            consult_no="CON20260513001",
            customer_id=cust_main.id,
            consultant_emp_id=e1.id,
            doctor_emp_id=e3.id,
            chief_complaint="面部松弛、法令纹加深",
            diagnosis_summary="建议能量类联合补水",
            consult_at=datetime(2026, 5, 13, 14, 30, 0),
        )
        db.add(consult_main)
        db.flush()

        plan = MaTreatmentPlan(
            plan_no="TP20260513001",
            customer_id=cust_main.id,
            consultation_id=consult_main.id,
            consultant_emp_id=e1.id,
            total_list_amount=19600,
            discount_amount=1800,
            status="confirmed",
        )
        db.add(plan)
        db.flush()
        db.add_all(
            [
                MaTreatmentPlanLine(
                    plan_id=plan.id,
                    sku_id=sku_ulthera.id,
                    qty=1,
                    unit_price=11800,
                    line_amount=11800,
                ),
                MaTreatmentPlanLine(
                    plan_id=plan.id,
                    sku_id=sku_water.id,
                    qty=1,
                    unit_price=2680,
                    line_amount=2680,
                ),
                MaTreatmentPlanLine(
                    plan_id=plan.id,
                    sku_id=sku_juvederm.id,
                    qty=1,
                    unit_price=6800,
                    line_amount=6800,
                ),
            ]
        )

        quote = MaQuotation(
            quote_no="QT20260513001",
            customer_id=cust_main.id,
            plan_id=plan.id,
            sales_id=sp1.id,
            amount=17800,
            valid_until=date(2026, 5, 31),
            status="accepted",
        )
        db.add(quote)
        db.flush()

        opp_main = opps[0]
        order = MaOrder(
            order_no="SO20260513001",
            branch_id=b1.id,
            customer_id=cust_main.id,
            sales_id=sp1.id,
            opp_id=opp_main.id,
            order_type="service",
            total_amount=17800,
            paid_amount=17800,
            order_status="paid",
            ordered_at=datetime(2026, 5, 13, 15, 10, 0),
        )
        db.add(order)
        db.flush()

        ol_ulthera = MaOrderLine(
            order_id=order.id,
            sku_id=sku_ulthera.id,
            qty=1,
            unit_price=11800,
            discount_share=1200,
            line_amount=10600,
        )
        ol_water = MaOrderLine(
            order_id=order.id,
            sku_id=sku_water.id,
            qty=1,
            unit_price=2680,
            discount_share=300,
            line_amount=2380,
        )
        ol_juve = MaOrderLine(
            order_id=order.id,
            sku_id=sku_juvederm.id,
            qty=1,
            unit_price=6800,
            discount_share=300,
            line_amount=4820,
        )
        db.add_all([ol_ulthera, ol_water, ol_juve])
        db.flush()

        pay_main = MaPayment(
            pay_no="PAY2026051300001",
            order_id=order.id,
            pay_channel="wechat_native",
            amount=17800,
            pay_time=datetime(2026, 5, 13, 15, 12, 0),
            third_trade_no="wx4200001234567890",
            status="success",
        )
        db.add(pay_main)
        db.flush()

        db.add_all(
            [
                MaCommissionDetail(
                    order_id=order.id,
                    sales_id=sp1.id,
                    sku_id=sku_ulthera.id,
                    base_amount=10600,
                    commission_amount=530,
                    settlement_month="2026-05",
                    status="accrued",
                ),
                MaCommissionDetail(
                    order_id=order.id,
                    sales_id=sp1.id,
                    sku_id=sku_water.id,
                    base_amount=2380,
                    commission_amount=119,
                    settlement_month="2026-05",
                    status="accrued",
                ),
                MaCommissionDetail(
                    order_id=order.id,
                    sales_id=sp1.id,
                    sku_id=sku_juvederm.id,
                    base_amount=4820,
                    commission_amount=289,
                    settlement_month="2026-05",
                    status="paid",
                ),
            ]
        )

        db.add(
            MaDoctorCommissionSplit(
                order_line_id=ol_ulthera.id,
                doctor_emp_id=e3.id,
                split_pct=12,
                amount=1272,
            )
        )

        db.add(
            MaContract(
                contract_no="CT20260513001",
                order_id=order.id,
                customer_id=cust_main.id,
                template_code="SVC-2026-A",
                signed_at=datetime(2026, 5, 13, 15, 20, 0),
                pdf_url="/contracts/demo/CT20260513001.pdf",
                status="signed",
            )
        )

        db.add_all(
            [
                MaDepositLedger(
                    customer_id=cust_main.id,
                    order_id=order.id,
                    amount=3000,
                    direction="in",
                    reason="定金",
                ),
                MaDepositLedger(
                    customer_id=cust_main.id,
                    order_id=order.id,
                    amount=3000,
                    direction="out",
                    reason="转实收抵扣",
                ),
            ]
        )

        db.add(
            MaRefund(
                refund_no="RF20260514001",
                order_id=order.id,
                payment_id=pay_main.id,
                amount=200,
                reason="活动差价退还",
                approved_by_emp_id=e2.id,
                status="done",
            )
        )

        db.add(
            MaGiftWithPurchase(
                order_id=order.id,
                gift_sku_id=sku_gift_mask.id,
                qty=2,
                campaign_code="CAM-202605",
            )
        )

        order_inst = MaOrder(
            order_no="SO20260515002",
            branch_id=b1.id,
            customer_id=custs[1].id,
            sales_id=sp1.id,
            opp_id=opps[1].id,
            order_type="service",
            total_amount=24000,
            paid_amount=6000,
            order_status="partial_paid",
            ordered_at=datetime(2026, 5, 15, 11, 0, 0),
        )
        db.add(order_inst)
        db.flush()
        db.add(
            MaOrderLine(
                order_id=order_inst.id,
                sku_id=sku_cool.id,
                bundle_id=None,
                qty=2,
                unit_price=12000,
                discount_share=0,
                line_amount=24000,
            )
        )
        db.add(
            MaPayment(
                pay_no="PAY2026051500002",
                order_id=order_inst.id,
                pay_channel="alipay",
                amount=6000,
                pay_time=datetime(2026, 5, 15, 11, 5, 0),
                status="success",
            )
        )
        db.flush()

        iplan = MaInstallmentPlan(
            order_id=order_inst.id,
            total_terms=6,
            down_payment=6000,
            monthly_amount=3000,
            finance_partner="演示分期合作方",
            status="active",
        )
        db.add(iplan)
        db.flush()
        for t in range(1, 7):
            db.add(
                MaInstallmentSchedule(
                    plan_id=iplan.id,
                    term_no=t,
                    due_date=date(2026, 6, 1) + timedelta(days=30 * (t - 1)),
                    amount=3000,
                    paid_at=datetime(2026, 5, 15, 11, 10) if t == 1 else None,
                    status="paid" if t == 1 else "due",
                )
            )

        order_small = MaOrder(
            order_no="SO20260516003",
            branch_id=b1.id,
            customer_id=custs[2].id,
            sales_id=sp2.id,
            opp_id=opps[2].id,
            order_type="service",
            total_amount=3960,
            paid_amount=3960,
            order_status="paid",
            ordered_at=datetime(2026, 5, 16, 16, 0, 0),
        )
        db.add(order_small)
        db.flush()
        db.add(
            MaOrderLine(
                order_id=order_small.id,
                sku_id=sku_photon.id,
                bundle_id=pkg_photon3.id,
                qty=1,
                unit_price=3960,
                discount_share=0,
                line_amount=3960,
            )
        )
        db.add(
            MaPayment(
                pay_no="PAY2026051600003",
                order_id=order_small.id,
                pay_channel="pos",
                amount=3960,
                pay_time=datetime(2026, 5, 16, 16, 2, 0),
                status="success",
            )
        )

        for i, c in enumerate(custs):
            db.add(
                MaSalesTarget(
                    branch_id=c.branch_id,
                    sales_id=c.owner_sales_id,
                    target_month="2026-05",
                    revenue_target=400000 + i * 50000,
                    deal_count_target=30 + i,
                )
            )

        for d_off in range(10):
            db.add(
                MaDailySalesStat(
                    branch_id=b1.id,
                    stat_date=date(2026, 5, 1) + timedelta(days=d_off),
                    new_leads=5 + d_off,
                    appt_count=15 + d_off,
                    visit_count=10 + d_off,
                    order_count=3 + (d_off % 4),
                    revenue=80000 + d_off * 12000,
                )
            )
        for d_off in range(5):
            db.add(
                MaDailySalesStat(
                    branch_id=b2.id,
                    stat_date=date(2026, 5, 1) + timedelta(days=d_off * 2),
                    new_leads=3 + d_off,
                    appt_count=8,
                    visit_count=6,
                    order_count=2,
                    revenue=45000 + d_off * 8000,
                )
            )

        tpl = MaCouponTemplate(
            code="NEW520",
            name="新客520代金券",
            discount_type="fixed",
            discount_value=520,
            min_spend=5000,
            valid_days=60,
        )
        tpl2 = MaCouponTemplate(
            code="SUMMER88",
            name="初夏满减88",
            discount_type="fixed",
            discount_value=88,
            min_spend=2000,
            valid_days=30,
        )
        db.add_all([tpl, tpl2])
        db.flush()
        for i, c in enumerate(custs[:5]):
            db.add(
                MaCouponIssue(
                    template_id=tpl.id if i % 2 == 0 else tpl2.id,
                    customer_id=c.id,
                    coupon_code=f"CPN-DEMO-{i:04d}",
                    status=["unused", "used"][i % 2],
                    used_order_id=order.id if i == 1 else None,
                )
            )

        for i, c in enumerate(custs):
            db.add(
                MaMemberCard(
                    card_no=f"MC-DEMO-{i+1:05d}",
                    customer_id=c.id,
                    tier=["normal", "silver", "gold", "platinum"][i % 4],
                    balance=100 * i,
                    points_balance=500 + i * 200,
                    opened_at=date(2026, 1, 1) + timedelta(days=i * 10),
                )
            )
            db.add(
                MaPointsLedger(
                    customer_id=c.id,
                    change_points=100 + i * 50,
                    biz_type="signup_bonus",
                    ref_order_id=None,
                )
            )
            db.add(
                MaPointsLedger(
                    customer_id=c.id,
                    change_points=200,
                    biz_type="consume_reward",
                    ref_order_id=order.id if c.id == cust_main.id else order_small.id,
                )
            )

        camp = MaMarketingCampaign(
            campaign_code="CAM-202605",
            name="初夏紧肤季",
            branch_id=b1.id,
            start_at=datetime(2026, 5, 1, 0, 0, 0),
            end_at=datetime(2026, 5, 31, 23, 59, 59),
            budget=200000,
            utm_source=src_xhs.name,
        )
        camp2 = MaMarketingCampaign(
            campaign_code="CAM-618",
            name="618大促预热",
            branch_id=None,
            start_at=datetime(2026, 6, 1, 0, 0, 0),
            end_at=datetime(2026, 6, 20, 23, 59, 59),
            budget=500000,
            utm_source="multi",
        )
        db.add_all([camp, camp2])
        db.flush()

        for c in custs[:6]:
            db.add(MaCampaignEnrollment(campaign_id=camp.id, customer_id=c.id))
        db.add(MaCampaignEnrollment(campaign_id=camp2.id, customer_id=custs[7].id))

        db.add(
            MaReferralReward(
                referrer_customer_id=custs[2].id,
                referee_customer_id=custs[0].id,
                order_id=order.id,
                reward_points=800,
                reward_cash=300,
                status="granted",
            )
        )

        db.flush()
        visit_main = db.scalars(
            select(MaVisitRecord)
            .where(MaVisitRecord.customer_id == cust_main.id)
            .order_by(MaVisitRecord.id)
            .limit(1)
        ).first()
        if visit_main:
            db.add(
                MaSatisfactionSurvey(
                    customer_id=cust_main.id,
                    visit_id=visit_main.id,
                    nps_score=9,
                    comment="整体满意，预约顺畅",
                )
            )

        db.add(
            MaAftercareTask(
                customer_id=cust_main.id,
                order_id=order.id,
                task_type="day1_wechat",
                due_at=datetime(2026, 5, 14, 18, 0, 0),
                assign_emp_id=e1.id,
                status="done",
            )
        )
        db.add(
            MaAftercareTask(
                customer_id=custs[3].id,
                order_id=order_small.id,
                task_type="day7_call",
                due_at=datetime(2026, 5, 25, 10, 0, 0),
                assign_emp_id=e5.id,
                status="open",
            )
        )

        db.add(
            MaComplaintTicket(
                ticket_no="TK20260501001",
                customer_id=custs[4].id,
                order_id=None,
                category="营销骚扰",
                description="希望减少短信频次，已备注免打扰",
                owner_emp_id=e2.id,
                status="closed",
            )
        )
        db.add(
            MaComplaintTicket(
                ticket_no="TK20260502002",
                customer_id=cust_main.id,
                order_id=order.id,
                category="效果争议",
                description="术后一周肿胀，已安排复诊",
                owner_emp_id=e1.id,
                status="investigating",
            )
        )

        db.add_all(
            [
                MaInventoryBatch(
                    branch_id=b1.id,
                    sku_id=sku_juvederm.id,
                    material_name="乔雅登雅致",
                    batch_no="ALLER-2025-088",
                    qty=48,
                    expiry_date=date(2027, 8, 1),
                    unit_cost=3100,
                ),
                MaInventoryBatch(
                    branch_id=b1.id,
                    sku_id=sku_water.id,
                    material_name="海月兰长效水光",
                    batch_no="HYDRO-2026-015",
                    qty=200,
                    expiry_date=date(2026, 12, 31),
                    unit_cost=900,
                ),
                MaInventoryBatch(
                    branch_id=b2.id,
                    sku_id=None,
                    material_name="一次性铺巾",
                    batch_no="DISPOS-001",
                    qty=5000,
                    expiry_date=None,
                    unit_cost=0.35,
                ),
            ]
        )

        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    from .init_db import init_database

    init_database()
    if seed_if_empty():
        print("✅ 医美销售演示数据已全量写入")
    else:
        print("ℹ️ 集团数据已存在，已尝试补全空表（见 init_database 日志）")
